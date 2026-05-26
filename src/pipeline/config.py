"""Pipeline configuration and execution backend management."""
import os
from enum import Enum
from pathlib import Path


class ExecutionBackend(str, Enum):
    AUTO = "auto"
    LOCAL = "local"
    WSL2 = "wsl2"
    DOCKER = "docker"
    REMOTE = "remote"


STEP_WEIGHTS: dict[str, str] = {
    "import": "light",
    "find-spots": "medium",
    "index": "light",
    "integrate": "medium",
    "scale": "medium",
    "merge": "light",
    "molecular-replacement": "heavy",
    "refine": "heavy",
    "validate": "light",
}

WEIGHT_CONCURRENCY: dict[str, int] = {
    "light": 4,
    "medium": 2,
    "heavy": 1,
}

PIPELINE_STEPS = [
    "import",
    "find-spots",
    "index",
    "integrate",
    "scale",
    "merge",
    "molecular-replacement",
    "refine",
    "validate",
]

STEP_DEPENDENCIES: dict[str, list[str]] = {
    "find-spots": ["import"],
    "index": ["find-spots"],
    "integrate": ["index"],
    "scale": ["integrate"],
    "merge": ["scale"],
    "molecular-replacement": ["merge"],
    "refine": ["molecular-replacement"],
    "validate": ["refine"],
}


class PipelineConfig:
    def __init__(
        self,
        backend: ExecutionBackend = ExecutionBackend.AUTO,
        wsl2_distro: str = "Ubuntu-22.04",
        data_root: Path | None = None,
        nproc: int | None = None,
        max_workers: int = 2,
    ):
        self.backend = backend
        self.wsl2_distro = wsl2_distro
        self.data_root = data_root or Path(__file__).parent.parent.parent / "data"
        self.nproc = nproc or os.cpu_count() or 4
        self.max_workers = max_workers

    def to_dict(self) -> dict:
        return {
            "backend": self.backend.value,
            "wsl2_distro": self.wsl2_distro,
            "data_root": str(self.data_root),
            "nproc": self.nproc,
            "max_workers": self.max_workers,
        }
