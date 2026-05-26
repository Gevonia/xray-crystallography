"""Runtime detection of available crystallography engines."""
import importlib
from pathlib import Path

from src.pipeline.phenix_paths import (
    has_phenix, has_tool, phenix_bin, phenix_root,
)


class DependencyChecker:
    @staticmethod
    def _check_module(name: str) -> bool:
        try:
            importlib.import_module(name)
            return True
        except ImportError:
            return False

    @staticmethod
    def check_dials() -> bool:
        try:
            from dials.command_line.find_spots import run  # noqa: F401
            return True
        except (ImportError, ModuleNotFoundError):
            return False

    @staticmethod
    def check_phenix() -> bool:
        return has_phenix()

    @staticmethod
    def check_phaser() -> bool:
        return has_tool("phaser")

    @staticmethod
    def check_ccp4() -> bool:
        return has_tool("phaser")  # PHENIX bundles PHASER

    @classmethod
    def get_status(cls) -> dict:
        root = phenix_root()
        return {
            "fabio": cls._check_module("fabio"),
            "dials": cls.check_dials(),
            "cctbx": cls._check_module("cctbx"),
            "reciprocalspaceship": cls._check_module("reciprocalspaceship"),
            "gemmi": cls._check_module("gemmi"),
            "phenix": cls.check_phenix(),
            "phaser": cls.check_phaser(),
            "ccp4": cls.check_ccp4(),
            "phenix_path": str(root) if root else None,
            "phenix_bin": str(phenix_bin()) if phenix_bin() else None,
        }
