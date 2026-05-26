r"""PHENIX installation path resolver.

Multi-tier detection for Windows-native PHENIX:
  1. User explicit override  (configure_phenix_path / PipelineConfig)
  2. Environment variable     (PHENIX, PHENIX_ROOT)
  3. Windows registry         (HKLM\SOFTWARE\Phenix\InstallPath)
  4. Filesystem glob scan     (D:\ProgramData\phenix-*, etc.)
  5. Hardcoded fallback list

All detection is lazy — nothing runs at import time.
Call configure_phenix_path() or has_phenix() to trigger.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

HARDCODED_FALLBACKS = [
    Path("D:/ProgramData/phenix-2.0-5936"),
    Path("C:/Phenix"),
    Path("C:/Program Files/Phenix"),
]

GLOB_PATTERNS = [
    "D:/ProgramData/phenix-*",
    "D:/phenix-*",
    "C:/phenix-*",
    "C:/Program Files/phenix-*",
]


class PhenixResolver:
    def __init__(self):
        self._user_path: str | None = None
        self._cached_root: Path | None = None
        self._cached_bin: Path | None = None
        self._resolved: bool = False  # False = not yet tried

    # -- public API --

    def resolve(self) -> Path | None:
        """Return PHENIX root directory, or None. Results are cached."""
        if self._resolved:
            return self._cached_root
        self._cached_root = self._detect()
        self._cached_bin = (
            self._cached_root / "Library" / "bin"
            if self._cached_root else None
        )
        self._resolved = True
        if self._cached_root:
            logger.info("PHENIX resolved to %s", self._cached_root)
        else:
            logger.warning("PHENIX not found")
        return self._cached_root

    def bin_dir(self) -> Path | None:
        self.resolve()
        return self._cached_bin

    def has_phenix(self) -> bool:
        return self.resolve() is not None

    def has_tool(self, tool: str) -> bool:
        bin_dir = self.bin_dir()
        if not bin_dir:
            return False
        return (bin_dir / f"phenix.{tool}.bat").exists()

    def get_cmd(self, tool: str, *args: str) -> list[str]:
        bin_dir = self.bin_dir()
        if not bin_dir:
            raise FileNotFoundError(
                "PHENIX not found. Set PHENIX path via API or environment variable."
            )
        bat = bin_dir / f"phenix.{tool}.bat"
        if not bat.exists():
            raise FileNotFoundError(f"PHENIX tool not found: phenix.{tool}")
        return [str(bat)] + list(args)

    def list_tools(self) -> list[str]:
        bin_dir = self.bin_dir()
        if not bin_dir:
            return []
        tools = []
        for f in sorted(bin_dir.glob("phenix.*.bat")):
            name = f.stem
            tool = name.replace("phenix.", "", 1)
            tools.append(tool)
        return tools

    def set_user_path(self, path: str | None):
        self._user_path = path
        self.reset()

    def get_resolved_path(self) -> str | None:
        root = self.resolve()
        return str(root) if root else None

    def get_detection_source(self) -> str:
        """Return which tier found PHENIX, for diagnostics."""
        if self._user_path:
            if self._verify(Path(self._user_path)):
                return "user_config"
        for var in ("PHENIX", "PHENIX_ROOT"):
            val = os.environ.get(var)
            if val and self._verify(Path(val)):
                return f"env:{var}"
        if self._from_registry():
            return "registry"
        for pattern in GLOB_PATTERNS:
            parent = Path(pattern).parent
            if parent.exists():
                for match in sorted(parent.glob(Path(pattern).name), reverse=True):
                    if self._verify(match):
                        return f"glob:{match}"
        for p in HARDCODED_FALLBACKS:
            if self._verify(p):
                return "fallback"
        return "not_found"

    def reset(self):
        self._cached_root = None
        self._cached_bin = None
        self._resolved = False

    # -- internal detection --

    def _detect(self) -> Path | None:
        # Tier 1: User explicit override (authoritative — no fallback)
        if self._user_path:
            return self._verify(Path(self._user_path))

        # Tier 2: Environment variable
        for var in ("PHENIX", "PHENIX_ROOT"):
            val = os.environ.get(var)
            if val:
                p = self._verify(Path(val))
                if p: return p

        # Tier 3: Windows registry
        p = self._from_registry()
        if p: return p

        # Tier 4: Glob scan
        for pattern in GLOB_PATTERNS:
            parent = Path(pattern).parent
            glob_name = Path(pattern).name
            if parent.exists():
                for match in sorted(parent.glob(glob_name), reverse=True):
                    p = self._verify(match)
                    if p: return p

        # Tier 5: Hardcoded fallback
        for p in HARDCODED_FALLBACKS:
            r = self._verify(p)
            if r: return r

        return None

    @staticmethod
    def _verify(root: Path) -> Path | None:
        bat = root / "Library" / "bin" / "phenix.refine.bat"
        return root if bat.exists() else None

    @staticmethod
    def _from_registry() -> Path | None:
        try:
            import winreg
            for hive, flags in [(winreg.HKEY_LOCAL_MACHINE, 0),
                                (winreg.HKEY_CURRENT_USER, 0)]:
                for key in (r"SOFTWARE\Phenix",
                            r"SOFTWARE\Wow6432Node\Phenix"):
                    try:
                        with winreg.OpenKey(hive, key, 0,
                                            winreg.KEY_READ | flags) as k:
                            val, _ = winreg.QueryValueEx(k, "InstallPath")
                            p = PhenixResolver._verify(Path(val))
                            if p: return p
                    except OSError:
                        continue
        except Exception:
            pass
        return None


# Module-level singleton
_resolver = PhenixResolver()


# -- Public API (delegates to singleton) --

def configure_phenix_path(path: str | None):
    """Set or clear the user-specified PHENIX path. Triggers re-detection."""
    _resolver.set_user_path(path)


def has_phenix() -> bool:
    return _resolver.has_phenix()


def has_tool(tool: str) -> bool:
    return _resolver.has_tool(tool)


def get_phenix_cmd(tool: str, *args: str) -> list[str]:
    return _resolver.get_cmd(tool, *args)


def list_available_tools() -> list[str]:
    return _resolver.list_tools()


def phenix_root() -> Path | None:
    return _resolver.resolve()


def phenix_bin() -> Path | None:
    return _resolver.bin_dir()


def get_resolved_path() -> str | None:
    return _resolver.get_resolved_path()


def get_detection_source() -> str:
    return _resolver.get_detection_source()
