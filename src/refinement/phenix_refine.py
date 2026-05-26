"""Structure refinement via phenix.refine — native Windows PHENIX subprocess wrapper."""
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

from src.pipeline.phenix_paths import has_tool, get_phenix_cmd


def _check_phenix() -> bool:
    return has_tool("refine")


def _run_phenix_refine(pdb_path: str, mtz_path: str, output_dir: Path,
                       n_macro_cycles: int = 5,
                       strategy: str = "individual_sites individual_adp rigid_body") -> dict:
    """Run phenix.refine via subprocess."""
    prefix = str(output_dir / "refined")

    cmd = get_phenix_cmd(
        "refine",
        pdb_path, mtz_path,
        f"main.number_of_macro_cycles={n_macro_cycles}",
        f"refinement.main.strategy={strategy}",
        "ordered_solvent=True",
        f"output.prefix={prefix}",
    )

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

    output = result.stdout + result.stderr
    rwork = _parse_refine_float(output, "R-work")
    rfree = _parse_refine_float(output, "R-free")
    rmsd_bonds = _parse_refine_float(output, "rms_bonds")
    rmsd_angles = _parse_refine_float(output, "rms_angles")

    pdb_out = Path(f"{prefix}_001.pdb")
    mtz_out = Path(f"{prefix}_001.mtz")

    return {
        "rwork": rwork,
        "rfree": rfree,
        "rmsd_bonds": rmsd_bonds,
        "rmsd_angles": rmsd_angles,
        "output_pdb": str(pdb_out) if pdb_out.exists() else None,
        "output_mtz": str(mtz_out) if mtz_out.exists() else None,
        "method": "phenix.refine",
    }


def _parse_refine_float(text: str, key: str) -> float:
    for line in text.splitlines():
        if key in line:
            try:
                parts = line.split(":")[-1].strip().split()
                return float(parts[0])
            except (ValueError, IndexError):
                pass
    return 0.0


def _fallback_refine(pdb_path: str | None, unit_cell: list,
                     space_group: str, output_dir: Path) -> dict:
    """Fallback: create geometry-annotated PDB when phenix is unavailable."""
    a, b, c, alpha, beta, gamma = unit_cell[:6]

    header = [
        f"HEADER    FALLBACK REFINEMENT",
        f"CRYST1 {a:8.3f} {b:8.3f} {c:8.3f} {alpha:6.2f} {beta:6.2f} {gamma:6.2f} {space_group:11s} 1",
        f"REMARK    phenix.refine is not available on this system.",
        f"REMARK    Install PHENIX on Linux/WSL2 to enable refinement.",
    ]

    if pdb_path and Path(pdb_path).exists():
        original = Path(pdb_path).read_text()
        # Inject CRYST1 if missing
        if "CRYST1" not in original:
            content = "\n".join(header + original.splitlines())
        else:
            content = original
    else:
        content = "\n".join(header + ["END"])

    out_pdb = output_dir / "refined_fallback.pdb"
    out_pdb.write_text(content)

    return {
        "rwork": 0.0,
        "rfree": 0.0,
        "rmsd_bonds": 0.0,
        "rmsd_angles": 0.0,
        "output_pdb": str(out_pdb),
        "output_mtz": None,
        "method": "fallback",
        "error": "phenix.refine not available — install PHENIX on Linux/WSL2",
    }


def run_refinement(job_dir: str | Path, params: dict | None = None) -> dict:
    """Run structure refinement.

    Inputs:
      job_dir/mr/mr_solution.pdb or fallback

    Outputs:
      job_dir/refine/refined.pdb
      job_dir/refine/refinement_result.json
    """
    job_dir = Path(job_dir)
    step_dir = job_dir / "refine"
    step_dir.mkdir(parents=True, exist_ok=True)

    # Find input PDB
    mr_pdb = None
    mr_dir = job_dir / "mr"
    if mr_dir.exists():
        for f in mr_dir.iterdir():
            if f.suffix == ".pdb":
                mr_pdb = str(f)
                break

    mtz_path = job_dir / "merge" / "merged.mtz"

    crystal_path = job_dir / "index" / "crystal.json"
    unit_cell = [50, 50, 50, 90, 90, 90]
    space_group = "P 1"
    if crystal_path.exists():
        with open(crystal_path) as f:
            crystal = json.load(f)
        unit_cell = crystal.get("unit_cell", unit_cell)
        space_group = crystal.get("space_group", space_group)

    if _check_phenix() and mtz_path.exists() and mr_pdb:
        result = _run_phenix_refine(mr_pdb, str(mtz_path), step_dir,
                                    n_macro_cycles=(params or {}).get("n_macro_cycles", 5),
                                    strategy=(params or {}).get("strategy",
                                        "individual_sites individual_adp rigid_body"))
    else:
        result = _fallback_refine(mr_pdb, unit_cell, space_group, step_dir)

    result["unit_cell"] = unit_cell
    result["space_group"] = space_group

    with open(step_dir / "refinement_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result
