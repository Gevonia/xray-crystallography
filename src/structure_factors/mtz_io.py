"""MTZ I/O and structure factor conversion utilities."""
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import reciprocalspaceship as rs
    HAS_RS = True
except ImportError:
    HAS_RS = False

try:
    import gemmi
    HAS_GEMMI = True
except ImportError:
    HAS_GEMMI = False


def read_mtz(path: str | Path) -> dict:
    """Read MTZ file, return reflection data dict."""
    if HAS_RS:
        dataset = rs.read_mtz(str(path))
        return {
            "n_reflections": len(dataset),
            "columns": list(dataset.columns),
            "space_group": str(dataset.spacegroup) if dataset.spacegroup else None,
            "cell": dataset.cell,
        }
    return {"error": "reciprocalspaceship not installed", "path": str(path)}


def intensities_to_amplitudes(intensities: list) -> dict:
    """Convert intensities to structure factor amplitudes (French-Wilson truncate).

    Simple sqrt approximation: F ≈ sqrt(I) for I > 0, F = 0 for I <= 0.
    Full French-Wilson requires CCTBX (ctbx.miller.array).
    """
    if not intensities:
        return {"n_amplitudes": 0}

    I = np.array(intensities, dtype=np.float64)
    positive = I > 0
    F = np.zeros_like(I)
    SIGF = np.zeros_like(I)

    F[positive] = np.sqrt(I[positive])
    SIGF[positive] = 0.5 * np.sqrt(I[positive]) / I[positive]

    n_positive = int(np.sum(positive))
    return {
        "n_amplitudes": n_positive,
        "f_mean": float(np.mean(F[positive])) if n_positive > 0 else 0.0,
        "f_max": float(np.max(F)) if n_positive > 0 else 0.0,
        "fraction_positive": float(n_positive / len(I)) if len(I) > 0 else 0.0,
        "method": "simple_sqrt_truncate",
    }


def generate_free_r_flags(n_reflections: int, fraction: float = 0.05) -> dict:
    """Generate random free R flag set. Real implementation uses CCTBX."""
    rng = np.random.RandomState(42)
    flags = rng.choice([0, 1], size=n_reflections, p=[1 - fraction, fraction])
    n_free = int(np.sum(flags))
    return {
        "n_total": n_reflections,
        "n_free": n_free,
        "n_work": int(n_reflections - n_free),
        "fraction": fraction,
        "flags": flags.tolist(),
    }


def create_mtz_summary(job_dir: str | Path) -> dict:
    """Create a summary of MTZ-format data, for frontend display."""
    job_dir = Path(job_dir)
    result = {"has_mtz": False, "has_merge": False}

    mtz_path = job_dir / "merge" / "merged.mtz"
    if mtz_path.exists():
        result["has_mtz"] = True
        result["mtz_size_kb"] = round(mtz_path.stat().st_size / 1024, 1)
        if HAS_RS:
            try:
                info = read_mtz(mtz_path)
                result.update(info)
            except Exception as e:
                result["mtz_error"] = str(e)

    merge_json = job_dir / "merge" / "merged_reflections.json"
    if merge_json.exists():
        result["has_merge"] = True
        with open(merge_json) as f:
            merge_data = json.load(f)
        result["n_reflections"] = merge_data.get("n_reflections", 0)
        result["space_group"] = merge_data.get("space_group")
        result["unit_cell"] = merge_data.get("unit_cell")

    return result
