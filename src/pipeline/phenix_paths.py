"""PHENIX installation path resolver for Windows native PHENIX 2.0.

Detects PHENIX at known install locations and provides a unified
command builder for all PHENIX tools (phenix.refine, phenix.phaser, phenix.molprobity, etc.).
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Known installation paths — searched in order
KNOWN_PATHS = [
    Path("D:/ProgramData/phenix-2.0-5936"),
    Path("C:/Phenix"),
    Path("C:/Program Files/Phenix"),
]


def _find_phenix_root() -> Path | None:
    """Auto-detect PHENIX installation root."""
    for candidate in KNOWN_PATHS:
        bin_dir = candidate / "Library" / "bin"
        if (bin_dir / "phenix.refine.bat").exists():
            return candidate
    return None


_PHENIX_ROOT: Path | None = _find_phenix_root()
_PHENIX_BIN: Path | None = _PHENIX_ROOT / "Library" / "bin" if _PHENIX_ROOT else None


def phenix_root() -> Path | None:
    return _PHENIX_ROOT


def phenix_bin() -> Path | None:
    return _PHENIX_BIN


def has_phenix() -> bool:
    return _PHENIX_BIN is not None


def has_tool(tool: str) -> bool:
    """Check if a specific PHENIX tool is available, e.g. 'refine', 'phaser', 'molprobity'."""
    if not _PHENIX_BIN:
        return False
    return (_PHENIX_BIN / f"phenix.{tool}.bat").exists()


def get_phenix_cmd(tool: str, *args: str) -> list[str]:
    """Build command list for a PHENIX tool.

    Example:
        get_phenix_cmd("refine", "model.pdb", "data.mtz", "nproc=4")
        → ["D:/ProgramData/phenix-2.0-5936/Library/bin/phenix.refine.bat",
           "model.pdb", "data.mtz", "nproc=4"]
    """
    if not _PHENIX_BIN:
        raise FileNotFoundError(
            "PHENIX not found. Searched: " + ", ".join(str(p) for p in KNOWN_PATHS))
    bat = _PHENIX_BIN / f"phenix.{tool}.bat"
    if not bat.exists():
        raise FileNotFoundError(f"PHENIX tool not found: phenix.{tool}")
    return [str(bat)] + list(args)


def list_available_tools() -> list[str]:
    """List all phenix.*.bat tools found in bin directory."""
    if not _PHENIX_BIN:
        return []
    tools = []
    for f in sorted(_PHENIX_BIN.glob("phenix.*.bat")):
        name = f.stem  # e.g. "phenix.refine"
        tool = name.replace("phenix.", "", 1)
        tools.append(tool)
    return tools
