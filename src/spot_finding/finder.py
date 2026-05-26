"""Diffraction spot finding — DIALS wrapper with numpy fallback."""
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    from dials.command_line.find_spots import run as dials_find_spots
    HAS_DIALS = True
except ImportError:
    HAS_DIALS = False
    logger.info("DIALS not available — using numpy fallback for spot finding")


def _find_spots_numpy(data: np.ndarray, min_spot_size: int = 3,
                      threshold_sigma: float = 5.0) -> dict:
    """Simple local-maxima spot detection for testing/demo without DIALS."""
    from scipy import ndimage

    # Background estimation via median filter
    bg = ndimage.median_filter(data, size=15)
    diff = data - bg
    noise = np.std(diff)
    threshold = threshold_sigma * noise

    # Find local maxima above threshold
    footprint = np.ones((min_spot_size, min_spot_size))
    local_max = ndimage.maximum_filter(diff, footprint=footprint) == diff
    spots_mask = local_max & (diff > threshold)
    spot_indices = np.argwhere(spots_mask)

    n_spots = len(spot_indices)
    intensities = data[spots_mask]

    # Estimate resolution from spot positions (radial distance from center)
    cy, cx = np.array(data.shape) / 2.0
    radii = np.sqrt((spot_indices[:, 0] - cy) ** 2 + (spot_indices[:, 1] - cx) ** 2)
    max_radius = radii.max() if len(radii) else 0

    return {
        "n_spots": n_spots,
        "spot_positions": spot_indices.tolist(),
        "spot_intensities": intensities.tolist(),
        "max_radius_px": float(max_radius),
        "method": "numpy_local_maxima",
        "threshold_sigma": threshold_sigma,
    }


def _find_spots_dials(experiments_path: str, output_dir: Path,
                      params: dict | None = None,
                      nproc: int = 4) -> dict:
    """Run DIALS find_spots on imported experiments."""
    default_params = {
        "min_spot_size": 3,
        "max_spot_size": 20,
        "nproc": nproc,
        "output": {
            "datablock_filename": str(output_dir / "strong.refl"),
        },
    }
    if params:
        default_params.update(params)

    args = [experiments_path]
    for k, v in default_params.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                args.append(f"{k}.{sk}={sv}")
        elif isinstance(v, bool):
            if v:
                args.append(f"{k}=True")
        else:
            args.append(f"{k}={v}")

    dials_find_spots(args)

    strong_path = output_dir / "strong.refl"
    if not strong_path.exists():
        raise RuntimeError("DIALS find_spots did not produce strong.refl")

    n_spots = _count_spots_from_refl(strong_path)
    return {
        "n_spots": n_spots,
        "method": "dials",
        "output_file": str(strong_path),
    }


def _count_spots_from_refl(refl_path: Path) -> int:
    """Count spots from a DIALS .refl file (pickle format)."""
    try:
        from dials.array_family import flex
        table = flex.reflection_table.from_file(str(refl_path))
        return len(table)
    except Exception:
        logger.warning("Could not read reflection table, spot count unknown")
        return -1


def find_spots(job_dir: str | Path, params: dict | None = None,
               nproc: int | None = None) -> dict:
    """Run spot finding. Uses DIALS if available, otherwise numpy fallback.

    Inputs expected in job_dir:
      job_dir/images/       — original image files
      job_dir/import/       — imported.npy (from image_import step)

    Outputs written to job_dir/find-spots/:
      spots.json            — spot positions and intensities
      strong.refl           — DIALS reflection table (if DIALS available)
    """
    job_dir = Path(job_dir)
    step_dir = job_dir / "find-spots"
    step_dir.mkdir(parents=True, exist_ok=True)

    nproc = nproc or 4

    # Load imported data
    imported_npy = job_dir / "import" / "imported.npy"
    if imported_npy.exists():
        data = np.load(str(imported_npy))
        if data.ndim == 3:
            data = data[0]  # use first frame for spot detection
    else:
        # Try reading images directly
        images_dir = job_dir / "images"
        image_files = sorted(images_dir.iterdir()) if images_dir.exists() else []
        if not image_files:
            raise FileNotFoundError(f"No images found in {job_dir}")
        import fabio
        data = fabio.open(str(image_files[0])).data.astype(np.float64)

    if HAS_DIALS:
        result = _find_spots_dials(
            experiments_path=str(job_dir / "import" / "imported.expt"),
            output_dir=step_dir,
            params=params,
            nproc=nproc,
        )
    else:
        threshold = (params or {}).get("threshold_sigma", 5.0)
        min_size = (params or {}).get("min_spot_size", 3)
        result = _find_spots_numpy(data, min_spot_size=min_size,
                                   threshold_sigma=threshold)

    # Always include spot positions in output for visualization
    if "spot_positions" not in result:
        result["spot_positions"] = []
        result["spot_intensities"] = []

    result["resolution_estimate"] = _estimate_resolution(data, result)

    with open(step_dir / "spots.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result


def _estimate_resolution(data: np.ndarray, spot_result: dict) -> float | None:
    """Crude resolution estimate from spot radial distribution."""
    positions = spot_result.get("spot_positions", [])
    if not positions:
        return None
    cy, cx = np.array(data.shape) / 2.0
    radii = []
    for pos in positions:
        r = np.sqrt((pos[0] - cy) ** 2 + (pos[1] - cx) ** 2)
        radii.append(r)
    radii = np.array(radii)
    # Resolution inversely proportional to max spot radius
    max_r = radii.max()
    # Rough: assume image diagonal = ~2.5 Å for a typical setup
    diagonal = np.sqrt(data.shape[0] ** 2 + data.shape[1] ** 2)
    resolution = (diagonal / max_r) * 1.5 if max_r > 0 else None
    return round(float(resolution), 2) if resolution else None
