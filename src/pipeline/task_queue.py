"""Resource-aware async task queue backed by ThreadPoolExecutor + SQLite."""
import json
import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection, Row
from typing import Callable

from .config import STEP_WEIGHTS, WEIGHT_CONCURRENCY

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self, db_path: Path, max_workers: int = 2):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._running_weights: dict[str, int] = {"light": 0, "medium": 0, "heavy": 0}
        self._pending: list[tuple[str, str, Callable, tuple, dict]] = []
        self._init_db()

    def _connect(self) -> Connection:
        conn = Connection(str(self.db_path))
        conn.row_factory = Row
        return conn

    def _init_db(self):
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                result_json TEXT
            )
        """)
        conn.commit()
        conn.close()

    def submit(self, job_id: str, step_name: str,
               fn: Callable, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        conn.execute(
            "INSERT INTO tasks (task_id, job_id, step_name, status, created_at) "
            "VALUES (?, ?, ?, 'queued', ?)",
            (task_id, job_id, step_name, now),
        )
        conn.commit()
        conn.close()

        weight = STEP_WEIGHTS.get(step_name, "medium")
        with self._lock:
            if self._can_start(weight):
                self._start_task(task_id, fn, args, kwargs, weight)
            else:
                self._pending.append((task_id, weight, fn, args, kwargs))

        return task_id

    def _can_start(self, weight: str) -> bool:
        limit = WEIGHT_CONCURRENCY.get(weight, 2)
        return self._running_weights[weight] < limit

    def _start_task(self, task_id: str, fn: Callable, args: tuple,
                    kwargs: dict, weight: str):
        self._running_weights[weight] += 1
        future = self.executor.submit(self._run_task, task_id, fn, args, kwargs, weight)
        self._futures[task_id] = future

    def _run_task(self, task_id: str, fn: Callable, args: tuple,
                  kwargs: dict, weight: str):
        conn = self._connect()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE tasks SET status = 'running', started_at = ? WHERE task_id = ?",
            (now, task_id),
        )
        conn.commit()

        status = "completed"
        error = ""
        result_json = ""
        try:
            result = fn(*args, **kwargs)
            result_json = json.dumps(result, default=str)
        except Exception as e:
            logger.exception("Task %s failed", task_id)
            status = "failed"
            error = str(e)

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE tasks SET status = ?, completed_at = ?, error = ?, result_json = ? "
            "WHERE task_id = ?",
            (status, now, error, result_json, task_id),
        )
        conn.commit()
        conn.close()

        with self._lock:
            self._running_weights[weight] -= 1
            self._futures.pop(task_id, None)
            self._drain_pending()

    def _drain_pending(self):
        remaining = []
        for task_id, weight, fn, args, kwargs in self._pending:
            if self._can_start(weight):
                self._start_task(task_id, fn, args, kwargs, weight)
            else:
                remaining.append((task_id, weight, fn, args, kwargs))
        self._pending = remaining

    def get_status(self, task_id: str) -> dict:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else {"status": "not_found"}

    def cancel(self, task_id: str) -> bool:
        conn = self._connect()
        conn.execute(
            "UPDATE tasks SET status = 'cancelled' WHERE task_id = ? "
            "AND status IN ('queued', 'running')",
            (task_id,),
        )
        conn.commit()
        conn.close()
        return True

    def get_job_tasks(self, job_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE job_id = ? ORDER BY created_at",
            (job_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def shutdown(self):
        self.executor.shutdown(wait=False)
