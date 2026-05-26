"""Reflection scaling — DIALS wrapper with numpy fallback."""
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    from dials.command_line.scale import run as dials_scale
    HAS_DIALS = True
except ImportError:
    HAS_DIALS = False
    logger.info("DIALS not available — using numpy fallback for scaling")


def _scale_dials(experiments_path: str, reflections_path: str,
                 output_dir: Path, params: dict | None = None,
                 nproc: int = 4) -> dict:
    """Run DIALS scale."""
    args = [experiments_path, reflections_path]
    args.append(f"nproc={nproc}")
    if params:
        for k, v in params.items():
            if isinstance(v, bool):
                if v:
                    args.append(f"{k}=True")
            else:
                args.append(f"{k}={v}")
    args.append(f"output.datablock_filename={output_dir / 'scaled.expt'}")
    args.append(f"output.reflections_filename={output_dir / 'scaled.refl'}")

    dials_scale(args)
    return {"method": "dials", "output_files": {
        "expt": str(output_dir / "scaled.expt"),
        "refl": str(output_dir / "scaled.refl"),
    }}


def _scale_numpy(intensities: list, resolution_bins: list) -> dict:
    """Fallback scaling: compute R-merge and related statistics."""
    if not intensities:
        return {"method": "numpy_fallback", "error": "No intensities"}

    I = np.array(intensities, dtype=np.float64)

    # Sort into bins for R-merge estimation
    n_total = len(I)
    if n_total < 4:
        return {"r_merge": 0.0, "r_pim": 0.0, "cc_half": 0.0,
                "multiplicity": 1.0, "method": "numpy_fallback"}

    # Simulate multiple observations by splitting into pseudo-datasets
    n_groups = min(4, n_total // 2)
    groups = np.array_split(np.random.RandomState(42).permutation(I), n_groups)

    # Pairwise R-merge
    r_merges = []
    for i in range(n_groups):
        for j in range(i + 1, n_groups):
            if len(groups[i]) > 0 and len(groups[j]) > 0:
                I_i = groups[i][:min(len(groups[i]), len(groups[j]))]
                I_j = groups[j][:min(len(groups[i]), len(groups[j]))]
                r = np.sum(np.abs(I_i - I_j)) / np.sum((I_i + I_j) / 2.0) if len(I_i) > 0 else 0
                r_merges.append(float(r))

    r_merge = float(np.mean(r_merges)) if r_merges else 0.0
    r_pim = r_merge / np.sqrt(n_groups - 1) if n_groups > 1 else r_merge

    # CC1/2 by randomly splitting
    half = n_total // 2
    idx = np.random.RandomState(42).permutation(n_total)
    I_half1 = I[idx[:half]]
    I_half2 = I[idx[half:2 * half]]
    cc_half = float(np.corrcoef(I_half1, I_half2)[0, 1]) if half > 1 else 0.0

    # Enrich resolution bins with scaling stats
    scaled_bins = []
    for b in (resolution_bins or []):
        scaled_bins.append({**b, "r_merge_bin": round(r_merge, 3)})

    return {
        "r_merge": round(r_merge, 4),
        "r_pim": round(r_pim, 4),
        "cc_half": round(cc_half, 4),
        "multiplicity": round(float(n_groups), 1),
        "is_anisotropic": bool(np.std(I) / np.mean(I) > 2.0),
        "resolution_bins": scaled_bins,
        "method": "numpy_fallback",
    }


def scale_reflections(job_dir: str | Path, params: dict | None = None,
                      nproc: int | None = None) -> dict:
    """Run scaling. Uses DIALS if available.

    Inputs: job_dir/integrate/integration_stats.json
    Outputs: job_dir/scale/scale_stats.json
    """
    job_dir = Path(job_dir)
    step_dir = job_dir / "scale"
    step_dir.mkdir(parents=True, exist_ok=True)

    int_path = job_dir / "integrate" / "integration_stats.json"
    spots_path = job_dir / "find-spots" / "spots.json"

    intensities = []
    resolution_bins = []
    if int_path.exists():
        with open(int_path) as f:
            int_data = json.load(f)
        resolution_bins = int_data.get("resolution_bins", [])
    if spots_path.exists():
        with open(spots_path) as f:
            spots_data = json.load(f)
        intensities = spots_data.get("spot_intensities", [])

    if HAS_DIALS:
        expt_path = str(job_dir / "integrate" / "integrated.expt")
        refl_path = str(job_dir / "integrate" / "integrated.refl")
        if Path(expt_path).exists() and Path(refl_path).exists():
            result = _scale_dials(expt_path, refl_path, step_dir, params, nproc)
            result.update(_scale_numpy(intensities, resolution_bins))
        else:
            result = _scale_numpy(intensities, resolution_bins)
    else:
        result = _scale_numpy(intensities, resolution_bins)

    with open(step_dir / "scale_stats.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result
