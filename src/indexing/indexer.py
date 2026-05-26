"""Crystal lattice indexing and space group assignment — DIALS wrapper with fallback."""
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    from dials.command_line.index import run as dials_index
    HAS_DIALS = True
except ImportError:
    HAS_DIALS = False
    logger.info("DIALS not available — using numpy fallback for indexing")

BRAVAIS_LATTICES = {
    "aP": "Triclinic",
    "mP": "Monoclinic (primitive)",
    "mC": "Monoclinic (C-centered)",
    "oP": "Orthorhombic (primitive)",
    "oC": "Orthorhombic (C-centered)",
    "oF": "Orthorhombic (F-centered)",
    "oI": "Orthorhombic (I-centered)",
    "tP": "Tetragonal (primitive)",
    "tI": "Tetragonal (I-centered)",
    "hP": "Hexagonal (primitive)",
    "hR": "Rhombohedral",
    "cP": "Cubic (primitive)",
    "cF": "Cubic (F-centered)",
    "cI": "Cubic (I-centered)",
}

COMMON_SPACE_GROUPS = [
    "P 1", "P 21", "C 2", "P 21 21 21", "C 2 2 21",
    "P 41 21 2", "P 43 21 2", "P 61", "P 31 2 1",
    "P 21 3", "I 21 3", "F 4 3 2",
]


def _index_dials(experiments_path: str, reflections_path: str,
                 output_dir: Path, params: dict | None = None,
                 nproc: int = 4) -> dict:
    """Run DIALS index."""
    args = [experiments_path, reflections_path]
    args.append(f"nproc={nproc}")

    if params:
        sg = params.get("space_group")
        if sg:
            args.append(f"space_group={sg}")
        uc = params.get("unit_cell")
        if uc:
            args.append(f"unit_cell={','.join(str(x) for x in uc)}")

    args.append(f"output.datablock_filename={output_dir / 'indexed.expt'}")
    args.append(f"output.reflections_filename={output_dir / 'indexed.refl'}")

    dials_index(args)

    indexed_refl = output_dir / "indexed.refl"
    if not indexed_refl.exists():
        raise RuntimeError("DIALS index did not produce indexed.refl")

    from dials.array_family import flex
    table = flex.reflection_table.from_file(str(indexed_refl))
    n_indexed = len(table)

    return {
        "n_indexed": n_indexed,
        "method": "dials",
        "output_files": {
            "expt": str(output_dir / "indexed.expt"),
            "refl": str(indexed_refl),
        },
    }


def _index_numpy(spots_positions: list, data_shape: tuple,
                 wavelength: float = 1.0, distance: float = 100.0,
                 pixel_size: float = 0.1) -> dict:
    """Fallback indexing: estimate unit cell from spot spacing patterns.

    Uses the radial distribution of spot positions to estimate
    the dominant reciprocal lattice vector lengths, then derives
    possible unit cell parameters.
    """
    if not spots_positions or len(spots_positions) < 6:
        return {"n_indexed": 0, "method": "numpy_fallback",
                "error": "Too few spots for indexing"}

    positions = np.array(spots_positions)
    cy, cx = np.array(data_shape) / 2.0

    # Convert to reciprocal space (approximate)
    dy = positions[:, 0] - cy
    dx = positions[:, 1] - cx

    # Radial distances in pixels → d* values (approximate)
    # d* = 1/d = 2*sin(theta)/lambda, theta ≈ atan(r * pixel_size / distance)
    radii_px = np.sqrt(dx**2 + dy**2)
    theta = np.arctan(radii_px * pixel_size / distance) / 2.0
    d_star = 2.0 * np.sin(theta) / wavelength

    # Find dominant spacings via histogram of d* values
    if len(d_star) > 5:
        hist, edges = np.histogram(d_star, bins=min(30, len(d_star) // 3))
        peaks = edges[np.argsort(hist)[-3:]]

        # Estimate unit cell edge from smallest d* peak
        d_min = 1.0 / peaks[-1] if peaks[-1] > 0 else 10.0
        a_est = round(d_min, 1)
    else:
        a_est = 50.0

    # Estimate crystal system from spot distribution symmetry
    angles = np.arctan2(dy, dx)
    angle_hist, _ = np.histogram(angles, bins=18)
    n_fold = _estimate_rotational_symmetry(angle_hist)

    crystal_system, possible_sg = _guess_crystal_system(n_fold)

    n_indexed = len(positions)
    fraction = n_indexed / max(n_indexed, len(spots_positions))

    return {
        "n_indexed": n_indexed,
        "fraction_indexed": round(fraction, 3),
        "unit_cell": [a_est, a_est, a_est, 90.0, 90.0, 90.0],
        "space_group": possible_sg[0],
        "possible_space_groups": possible_sg[:3],
        "crystal_system": crystal_system,
        "estimated_resolution": round(float(1.0 / d_star.max()) if d_star.size > 0 else 0, 1),
        "method": "numpy_fallback",
        "bravais_lattice": crystal_system,
    }


def _estimate_rotational_symmetry(angle_hist: np.ndarray) -> int:
    """Estimate rotational symmetry from angular distribution of spots."""
    n_bins = len(angle_hist)
    correlations = []
    for fold in [2, 3, 4, 6]:
        step = n_bins // fold
        if step == 0:
            continue
        scores = []
        for offset in range(step):
            slices = angle_hist[offset::step]
            scores.append(float(np.std(slices)))
        correlations.append((fold, np.mean(scores)))
    if not correlations:
        return 1
    best_fold = min(correlations, key=lambda x: x[1])[0]
    return best_fold


def _guess_crystal_system(n_fold: int) -> tuple[str, list[str]]:
    """Map rotational symmetry to crystal system and space groups."""
    if n_fold >= 6:
        return "Hexagonal", ["P 61", "P 31 2 1", "P 1"]
    elif n_fold == 4:
        return "Tetragonal", ["P 41 21 2", "P 43 21 2", "P 1"]
    elif n_fold == 3:
        return "Cubic", ["P 21 3", "I 21 3", "F 4 3 2"]
    elif n_fold == 2:
        return "Monoclinic", ["P 21", "C 2", "P 1"]
    else:
        return "Triclinic", ["P 1"]


def index_crystal(job_dir: str | Path, params: dict | None = None,
                  nproc: int | None = None) -> dict:
    """Run crystal indexing. Uses DIALS if available, numpy fallback otherwise.

    Inputs expected in job_dir:
      job_dir/find-spots/spots.json  — spot positions
      job_dir/import/imported.npy    — image data for geometry

    Outputs written to job_dir/index/:
      crystal.json                   — unit cell, space group, resolution
    """
    job_dir = Path(job_dir)
    step_dir = job_dir / "index"
    step_dir.mkdir(parents=True, exist_ok=True)

    nproc = nproc or 4

    spots_path = job_dir / "find-spots" / "spots.json"
    if spots_path.exists():
        with open(spots_path) as f:
            spots_data = json.load(f)
        spot_positions = spots_data.get("spot_positions", [])
    else:
        spot_positions = []

    # Load metadata for geometry
    meta_path = job_dir / "import" / "images_meta.json"
    wavelength = 1.0
    distance = 100.0
    px_size = 0.1
    data_shape = (512, 512)
    if meta_path.exists():
        with open(meta_path) as f:
            metas = json.load(f)
        if metas and "shape" in metas[0]:
            data_shape = tuple(metas[0]["shape"])
        if metas:
            wavelength = float(metas[0].get("wavelength", wavelength))
            distance = float(metas[0].get("detector_distance_mm", distance))

    if HAS_DIALS:
        expt_path = str(job_dir / "import" / "imported.expt")
        refl_path = str(job_dir / "find-spots" / "strong.refl")
        if Path(expt_path).exists() and Path(refl_path).exists():
            result = _index_dials(expt_path, refl_path, step_dir, params, nproc)
        else:
            result = _index_numpy(spot_positions, data_shape,
                                  wavelength, distance, px_size)
    else:
        result = _index_numpy(spot_positions, data_shape,
                              wavelength, distance, px_size)

    if "unit_cell" not in result:
        result["unit_cell"] = [50, 50, 50, 90, 90, 90]
    if "space_group" not in result:
        result["space_group"] = "P 1"

    with open(step_dir / "crystal.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result
