"""Pipeline orchestrator: state machine and step dispatch."""
import logging
import shutil
from pathlib import Path
from typing import Any

from .config import PIPELINE_STEPS, STEP_DEPENDENCIES, PipelineConfig
from .dependency_checker import DependencyChecker
from .state_store import JobStateStore
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)


class StepNotAvailableError(Exception):
    """Raised when a step's engine is not installed."""


class PipelineOrchestrator:
    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.config.data_root.mkdir(parents=True, exist_ok=True)
        db_path = self.config.data_root / "jobs.db"
        self.state_store = JobStateStore(db_path)
        self.task_queue = TaskQueue(
            self.config.data_root / "tasks.sqlite",
            max_workers=self.config.max_workers,
        )

    # -- Job CRUD --

    def create_job(self, name: str = "", params: dict | None = None) -> str:
        job_id = self.state_store.create_job(name=name, params=params)
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created job %s at %s", job_id, job_dir)
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        job = self.state_store.get_job(job_id)
        if job:
            job["pipeline"] = self._get_pipeline_status(job_id)
        return job

    def list_jobs(self) -> list[dict]:
        jobs = self.state_store.list_jobs()
        for j in jobs:
            j["pipeline"] = self._get_pipeline_status(j["job_id"])
        return jobs

    def delete_job(self, job_id: str):
        job_dir = self._job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        self.state_store.delete_job(job_id)

    # -- Image upload --

    def store_uploaded_images(self, job_id: str, file_paths: list[Path]) -> list[dict]:
        job_dir = self._job_dir(job_id)
        (job_dir / "images").mkdir(exist_ok=True)
        metas = []
        for fp in file_paths:
            dest = job_dir / "images" / fp.name
            shutil.copy2(fp, dest)
            metas.append({"filename": fp.name, "size": fp.stat().st_size})
        self.state_store.update_job(job_id, {"images": metas})
        return metas

    # -- Step execution --

    def run_step(self, job_id: str, step_name: str) -> dict:
        if step_name not in PIPELINE_STEPS:
            return {"error": f"Unknown step: {step_name}"}

        deps = STEP_DEPENDENCIES.get(step_name, [])
        state = self.state_store.get_job_state(job_id)
        for dep in deps:
            if state.get(dep) != "completed":
                return {"error": f"Dependency not met: {dep} is {state.get(dep, 'pending')}"}

        self.state_store.set_step_state(job_id, step_name, "queued")
        task_id = self.task_queue.submit(
            job_id, step_name, self._execute_step, job_id, step_name
        )
        return {"task_id": task_id, "step": step_name, "status": "queued"}

    def run_full_pipeline(self, job_id: str) -> list[dict]:
        results = []
        for step in PIPELINE_STEPS:
            state = self.state_store.get_job_state(job_id)
            if state.get(step) == "completed":
                results.append({"step": step, "status": "skipped"})
                continue
            result = self.run_step(job_id, step)
            results.append(result)
            if "error" in result:
                break
        return results

    # -- Internal dispatch --

    def _execute_step(self, job_id: str, step_name: str) -> dict:
        self.state_store.set_step_state(job_id, step_name, "running")
        job_dir = self._job_dir(job_id)
        step_dir = job_dir / step_name
        step_dir.mkdir(exist_ok=True)

        runners: dict[str, Any] = {
            "import": self._run_import,
            "find-spots": self._run_find_spots,
            "index": self._run_index,
            "integrate": self._run_integrate,
            "scale": self._run_scale,
            "merge": self._run_merge,
            "molecular-replacement": self._run_mr,
            "refine": self._run_refine,
            "validate": self._run_validate,
        }

        runner = runners.get(step_name)
        if not runner:
            raise ValueError(f"No runner for step: {step_name}")

        try:
            result = runner(job_id, job_dir, step_dir)
            self.state_store.set_step_state(job_id, step_name, "completed")
            self.state_store.set_step_result(job_id, step_name, result)
            return result
        except StepNotAvailableError:
            self.state_store.set_step_state(job_id, step_name, "skipped", "Engine not available")
            return {"status": "skipped", "reason": "engine not available"}
        except Exception:
            self.state_store.set_step_state(job_id, step_name, "failed", str(logger.exception))
            raise

    # -- Step implementations (stubs for Phase 1) --

    def _run_import(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        images_dir = job_dir / "images"
        if not images_dir.exists() or not list(images_dir.iterdir()):
            raise FileNotFoundError("No images uploaded. Upload images first.")

        image_paths = sorted(images_dir.iterdir())

        # Check fabio availability
        try:
            import fabio  # noqa: F401
        except ImportError:
            # Fallback: just copy metadata for .npy files
            import json
            import numpy as np
            metas = []
            for fp in image_paths:
                if fp.suffix == '.npy':
                    arr = np.load(str(fp))
                    metas.append({"filename": fp.name, "shape": list(arr.shape),
                                  "dtype": str(arr.dtype), "format": "numpy"})
            with open(step_dir / "images_meta.json", "w") as f:
                json.dump(metas, f, indent=2)
            if metas and image_paths:
                np.save(str(step_dir / "imported.npy"), np.load(str(image_paths[0])))
            result = {"n_images": len(metas), "formats": {"numpy": len(metas)},
                      "metadata": metas, "fallback": True}
            self.state_store.update_job(job_id, {"import_meta": result["metadata"]})
            return result

        from src.image_import.reader import import_images
        result = import_images(image_paths, output_dir=step_dir)
        self.state_store.update_job(job_id, {"import_meta": result["metadata"]})
        return result

    def _run_find_spots(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.spot_finding.finder import find_spots

        job = self.state_store.get_job(job_id) or {}
        # params_json is unpacked by get_job; extract original params dict
        raw_params = job.get("params_json", "{}")
        if isinstance(raw_params, str):
            import json as _json
            raw_params = _json.loads(raw_params)
        params = raw_params if isinstance(raw_params, dict) else {}

        result = find_spots(
            job_dir,
            params=params.get("spot_finding"),
            nproc=self.config.nproc,
        )
        n_spots = result.get("n_spots", 0)
        self.state_store.update_job(job_id, {
            "n_spots": n_spots,
            "resolution_estimate": result.get("resolution_estimate"),
        })
        return result

    def _run_index(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.indexing.indexer import index_crystal

        result = index_crystal(job_dir, nproc=self.config.nproc)
        self.state_store.update_job(job_id, {
            "unit_cell": result.get("unit_cell"),
            "space_group": result.get("space_group"),
            "crystal_system": result.get("crystal_system", ""),
        })
        return result

    def _run_integrate(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.integration.integrator import integrate

        result = integrate(job_dir, nproc=self.config.nproc)
        self.state_store.update_job(job_id, {
            "i_over_sigma": result.get("overall_i_over_sigma"),
            "completeness": result.get("completeness"),
        })
        return result

    def _run_scale(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.scaling.scaler import scale_reflections

        result = scale_reflections(job_dir, nproc=self.config.nproc)
        self.state_store.update_job(job_id, {
            "r_merge": result.get("r_merge"),
            "r_pim": result.get("r_pim"),
            "cc_half": result.get("cc_half"),
        })
        return result

    def _run_merge(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.scaling.merge import merge_and_export

        result = merge_and_export(job_dir)
        self.state_store.update_job(job_id, {
            "n_reflections": result.get("n_reflections"),
        })
        return result

    def _run_mr(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.molecular_replacement.phaser_wrapper import run_molecular_replacement

        job = self.state_store.get_job(job_id) or {}
        raw = job.get("params_json", "{}")
        if isinstance(raw, str):
            import json as _json
            raw = _json.loads(raw)
        params = raw if isinstance(raw, dict) else {}

        result = run_molecular_replacement(
            job_dir,
            search_model_path=params.get("search_model_path"),
            composition=params.get("composition"),
            n_molecules=params.get("n_molecules", 1),
            solvent_content=params.get("solvent_content", 0.5),
        )
        self.state_store.update_job(job_id, {
            "mr_solution_found": result.get("solution_found"),
            "mr_llg": result.get("log_likelihood_gain"),
            "mr_tfz": result.get("tfz_score"),
        })
        return result

    def _run_refine(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.refinement.phenix_refine import run_refinement

        job = self.state_store.get_job(job_id) or {}
        raw = job.get("params_json", "{}")
        if isinstance(raw, str):
            import json as _json
            raw = _json.loads(raw)
        params = raw if isinstance(raw, dict) else {}

        result = run_refinement(job_dir, params=params.get("refinement"))
        self.state_store.update_job(job_id, {
            "rwork": result.get("rwork"),
            "rfree": result.get("rfree"),
            "rmsd_bonds": result.get("rmsd_bonds"),
            "rmsd_angles": result.get("rmsd_angles"),
        })
        return result

    def _run_validate(self, job_id: str, job_dir: Path, step_dir: Path) -> dict:
        from src.refinement.validation import run_validation

        result = run_validation(job_dir)
        self.state_store.update_job(job_id, {
            "ramachandran_favored": result.get("ramachandran_favored"),
            "ramachandran_outliers": result.get("ramachandran_outliers"),
            "clash_score": result.get("clash_score"),
            "overall_score": result.get("overall_score"),
        })
        return result

    def cancel_job(self, job_id: str):
        tasks = self.task_queue.get_job_tasks(job_id)
        for t in tasks:
            self.task_queue.cancel(t["task_id"])

    # -- Helpers --

    def _job_dir(self, job_id: str) -> Path:
        return self.config.data_root / "jobs" / job_id

    def _get_pipeline_status(self, job_id: str) -> list[dict]:
        state = self.state_store.get_job_state(job_id)
        return [
            {"step": s, "status": state.get(s, "pending")}
            for s in PIPELINE_STEPS
        ]

    def get_system_status(self) -> dict:
        return {
            "dependencies": DependencyChecker.get_status(),
            "config": self.config.to_dict(),
        }
