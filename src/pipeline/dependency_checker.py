"""Runtime detection of available crystallography engines."""
import importlib
import shutil


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
        return shutil.which("phenix.refine") is not None

    @staticmethod
    def check_phaser() -> bool:
        return shutil.which("phaser") is not None

    @staticmethod
    def check_ccp4() -> bool:
        return shutil.which("ccp4-python") is not None

    @classmethod
    def get_status(cls) -> dict:
        return {
            "fabio": cls._check_module("fabio"),
            "dials": cls.check_dials(),
            "cctbx": cls._check_module("cctbx"),
            "reciprocalspaceship": cls._check_module("reciprocalspaceship"),
            "gemmi": cls._check_module("gemmi"),
            "phenix": cls.check_phenix(),
            "phaser": cls.check_phaser(),
            "ccp4": cls.check_ccp4(),
        }
