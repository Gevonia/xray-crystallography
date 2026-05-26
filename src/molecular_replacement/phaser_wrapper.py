"""Molecular replacement via PHASER — subprocess wrapper with fallback."""
import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import gemmi
    HAS_GEMMI = True
except ImportError:
    HAS_GEMMI = False


def _check_phaser() -> bool:
    return shutil.which("phaser") is not None


def _run_phaser_subprocess(mtz_path: str, search_pdb: str, output_dir: Path,
                           composition: dict | None = None,
                           n_molecules: int = 1,
                           solvent_content: float = 0.5) -> dict:
    """Run PHASER via subprocess with keyword input."""
    if not _check_phaser():
        raise FileNotFoundError("PHASER executable not found in PATH")

    keyword_file = output_dir / "phaser_input.key"
    output_root = str(output_dir / "mr_solution")

    keywords = f"""\
MODE MR_AUTO
HKLIn {mtz_path}
LABIn F=F SIGF=SIGF
ENSEMBLE {search_pdb} IDENTITY 1.0
COMPOSITION PROTEIN MW {composition.get('mw', 30000) if composition else 30000}
SEARCH NUMBER {n_molecules}
SOLVENT CONTENT {solvent_content}
ROOT {output_root}
"""

    keyword_file.write_text(keywords)
    result = subprocess.run(
        ["phaser", str(keyword_file)],
        capture_output=True, text=True, timeout=3600,
    )

    if result.returncode != 0:
        logger.error("PHASER failed: %s", result.stderr[-500:])
        return {"solution_found": False, "error": result.stderr[-200:]}

    # Parse output for solution metrics
    output = result.stdout
    llg = _parse_phaser_float(output, "LLG=")
    tfz = _parse_phaser_float(output, "TFZ=")

    return {
        "solution_found": llg > 10,
        "log_likelihood_gain": llg,
        "tfz_score": tfz,
        "method": "phaser",
        "output_pdb": str(Path(f"{output_root}.1.pdb")) if llg > 10 else None,
    }


def _parse_phaser_float(text: str, prefix: str) -> float:
    for line in text.splitlines():
        if prefix in line:
            try:
                parts = line.split(prefix)[1].strip().split()
                return float(parts[0])
            except (ValueError, IndexError):
                pass
    return 0.0


def _prepare_search_model(pdb_path: str | None, output_dir: Path) -> str | None:
    """Prepare/validate a search model PDB using gemmi."""
    if not pdb_path:
        return None

    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        return None

    if HAS_GEMMI:
        try:
            structure = gemmi.read_structure(str(pdb_path))
            # Strip non-protein atoms for MR
            sel = gemmi.Selection("(ATOM)")
            stripped = structure.clone()
            stripped.remove_invalid_atoms()
            out_path = str(output_dir / "search_model_clean.pdb")
            stripped.write_pdb(out_path)
            return out_path
        except Exception as e:
            logger.warning("gemmi model prep failed: %s", e)

    # Copy as-is
    import shutil
    dest = str(output_dir / "search_model.pdb")
    shutil.copy(str(pdb_path), dest)
    return dest


def _fallback_dummy_pdb(unit_cell: list, space_group: str,
                        output_dir: Path) -> dict:
    """Generate a minimal PDB for testing when PHASER is unavailable."""
    a, b, c, alpha, beta, gamma = unit_cell[:6]

    pdb_lines = [
        f"CRYST1 {a:8.3f} {b:8.3f} {c:8.3f} {alpha:6.2f} {beta:6.2f} {gamma:6.2f} {space_group:11s} 1",
        f"REMARK    Molecular replacement not available on this system.",
        f"REMARK    Install PHASER (CCP4) on Linux to enable MR.",
        "END",
    ]
    pdb_path = output_dir / "mr_solution_fallback.pdb"
    pdb_path.write_text("\n".join(pdb_lines))

    return {
        "solution_found": False,
        "log_likelihood_gain": 0.0,
        "tfz_score": 0.0,
        "method": "fallback",
        "error": "PHASER not available — install CCP4 on Linux/WSL2",
        "output_pdb": str(pdb_path),
    }


def run_molecular_replacement(job_dir: str | Path,
                               search_model_path: str | None = None,
                               composition: dict | None = None,
                               n_molecules: int = 1,
                               solvent_content: float = 0.5) -> dict:
    """Run molecular replacement.

    Inputs:
      job_dir/merge/merged.mtz
      search_model_path — optional PDB for search model

    Outputs:
      job_dir/mr/mr_solution.pdb
      job_dir/mr/mr_result.json
    """
    job_dir = Path(job_dir)
    step_dir = job_dir / "mr"
    step_dir.mkdir(parents=True, exist_ok=True)

    mtz_path = job_dir / "merge" / "merged.mtz"

    # Get crystal info
    crystal_path = job_dir / "index" / "crystal.json"
    unit_cell = [50, 50, 50, 90, 90, 90]
    space_group = "P 1"
    if crystal_path.exists():
        with open(crystal_path) as f:
            crystal = json.load(f)
        unit_cell = crystal.get("unit_cell", unit_cell)
        space_group = crystal.get("space_group", space_group)

    if _check_phaser() and mtz_path.exists():
        search_pdb = _prepare_search_model(search_model_path, step_dir)
        if search_pdb:
            result = _run_phaser_subprocess(
                str(mtz_path), search_pdb, step_dir,
                composition, n_molecules, solvent_content,
            )
        else:
            result = _fallback_dummy_pdb(unit_cell, space_group, step_dir)
    else:
        result = _fallback_dummy_pdb(unit_cell, space_group, step_dir)

    result["unit_cell"] = unit_cell
    result["space_group"] = space_group

    with open(step_dir / "mr_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result
