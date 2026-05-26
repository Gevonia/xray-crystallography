"""Data schemas for pipeline step inputs and results."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ImageSet:
    job_id: str
    image_paths: list[Path]
    n_images: int
    format: str
    metadata: dict = field(default_factory=dict)
    experiments_path: Optional[Path] = None
    reflections_path: Optional[Path] = None


@dataclass
class SpotFindingResult:
    experiments_path: Path
    reflections_path: Path
    n_spots: int
    resolution_range: tuple[float, float]
    spot_density: float
    i_over_sigma_mean: float


@dataclass
class IndexingResult:
    experiments_path: Path
    reflections_path: Path
    unit_cell: tuple[float, float, float, float, float, float]
    space_group: str
    space_group_number: int
    rmsd: float
    n_indexed: int
    fraction_indexed: float
    bravais_lattice: dict = field(default_factory=dict)
    resolution: float = 0.0


@dataclass
class IntegrationResult:
    experiments_path: Path
    reflections_path: Path
    n_integrated: int
    n_failed: int
    overall_i_over_sigma: float
    completeness: float
    resolution_bins: list[dict] = field(default_factory=list)


@dataclass
class ScalingResult:
    experiments_path: Path
    reflections_path: Path
    r_merge: float = 0.0
    r_pim: float = 0.0
    cc_half: float = 0.0
    completeness: float = 0.0
    multiplicity: float = 0.0
    is_anisotropic: bool = False
    resolution_bins: list[dict] = field(default_factory=list)


@dataclass
class MergeResult:
    mtz_path: Path
    space_group: str = ""
    unit_cell: tuple = ()
    resolution: float = 0.0
    merging_stats: dict = field(default_factory=dict)


@dataclass
class MolecularReplacementResult:
    solution_found: bool = False
    log_likelihood_gain: float = 0.0
    tfz_score: float = 0.0
    translation_z: float = 0.0
    r_factors: dict = field(default_factory=dict)
    output_pdb: Optional[Path] = None
    solution_details: list[dict] = field(default_factory=list)


@dataclass
class RefinementResult:
    rwork: float = 0.0
    rfree: float = 0.0
    rmsd_bonds: float = 0.0
    rmsd_angles: float = 0.0
    output_pdb: Path = field(default_factory=Path)
    output_mtz: Path = field(default_factory=Path)
    n_atoms: int = 0
    n_water: int = 0


@dataclass
class ValidationResult:
    ramachandran_favored: float = 0.0
    ramachandran_allowed: float = 0.0
    ramachandran_outliers: float = 0.0
    rotamer_outliers: float = 0.0
    clash_score: float = 0.0
    overall_score: float = 0.0
    report_path: Optional[Path] = None
