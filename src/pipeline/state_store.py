"""Job state persistence via SQLite."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection, Row

from .config import PIPELINE_STEPS


class JobStateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> Connection:
        conn = Connection(str(self.db_path))
        conn.row_factory = Row
        return conn

    def _init_db(self):
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                params_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'created',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_steps (
                job_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                result_json TEXT,
                PRIMARY KEY (job_id, step_name),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)
        conn.commit()
        conn.close()

    def create_job(self, name: str = "", params: dict | None = None) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        conn.execute(
            "INSERT INTO jobs (job_id, name, params_json, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'created', ?, ?)",
            (job_id, name, json.dumps(params or {}), now, now),
        )
        for step in PIPELINE_STEPS:
            conn.execute(
                "INSERT INTO job_steps (job_id, step_name, status) VALUES (?, ?, 'pending')",
                (job_id, step),
            )
        conn.commit()
        conn.close()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        job = dict(row)
        # Unpack params_json into top-level keys
        params = json.loads(job.get("params_json") or "{}")
        job.update(params)
        return job

    def list_jobs(self) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    KNOWN_COLUMNS = {"name", "status"}

    def update_job(self, job_id: str, updates: dict):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()

        # Separate known columns from arbitrary metadata
        set_parts = []
        values = []
        extra = {}
        for key, val in updates.items():
            if key in self.KNOWN_COLUMNS:
                set_parts.append(f"{key} = ?")
                values.append(val)
            else:
                extra[key] = val

        # Merge extra into params_json
        if extra:
            row = conn.execute(
                "SELECT params_json FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            current = json.loads(row["params_json"]) if row and row["params_json"] else {}
            current.update(extra)
            set_parts.append("params_json = ?")
            values.append(json.dumps(current))

        set_parts.append("updated_at = ?")
        values.append(now)
        values.append(job_id)

        conn.execute(
            f"UPDATE jobs SET {', '.join(set_parts)} WHERE job_id = ?", values
        )
        conn.commit()
        conn.close()

    def delete_job(self, job_id: str):
        conn = self._connect()
        conn.execute("DELETE FROM job_steps WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()
        conn.close()

    def set_step_state(self, job_id: str, step_name: str, status: str, error: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        if status == "running":
            conn.execute(
                "UPDATE job_steps SET status = ?, started_at = ?, error = ? "
                "WHERE job_id = ? AND step_name = ?",
                (status, now, error, job_id, step_name),
            )
        elif status in ("completed", "failed"):
            conn.execute(
                "UPDATE job_steps SET status = ?, completed_at = ?, error = ? "
                "WHERE job_id = ? AND step_name = ?",
                (status, now, error, job_id, step_name),
            )
        else:
            conn.execute(
                "UPDATE job_steps SET status = ?, error = ? WHERE job_id = ? AND step_name = ?",
                (status, error, job_id, step_name),
            )
        conn.commit()
        conn.close()

    def set_step_result(self, job_id: str, step_name: str, result: dict):
        conn = self._connect()
        conn.execute(
            "UPDATE job_steps SET result_json = ? WHERE job_id = ? AND step_name = ?",
            (json.dumps(result, default=str), job_id, step_name),
        )
        conn.commit()
        conn.close()

    def get_job_state(self, job_id: str) -> dict:
        conn = self._connect()
        rows = conn.execute(
            "SELECT step_name, status FROM job_steps WHERE job_id = ?", (job_id,)
        ).fetchall()
        conn.close()
        return {r["step_name"]: r["status"] for r in rows}

    def get_step_detail(self, job_id: str, step_name: str) -> dict | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM job_steps WHERE job_id = ? AND step_name = ?",
            (job_id, step_name),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
