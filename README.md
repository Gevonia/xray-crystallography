# X-ray Crystallography Pipeline

Protein crystal structure determination from X-ray diffraction images — fully automated pipeline with web interface.

## Overview

A Flask-based web application that orchestrates the complete crystallography workflow:

```
Diffraction Images → Spot Finding → Indexing → Integration → Scaling
    → Merging → Molecular Replacement → Refinement → Validation
```

Each step can run independently or as a full automated pipeline. Built on DIALS, PHENIX, and PHASER with numpy fallbacks for every computation step — the app works even without the full crystallography stack installed.

## Quick Start

```bash
# Clone
git clone https://github.com/Gevonia/xray-crystallography.git
cd xray-crystallography

# Install pip dependencies
pip install -r requirements.txt

# Start the server
python app.py
# → http://localhost:5101
```

For full crystallographic computation, install DIALS via conda:

```bash
conda env create -f environment.yml
conda activate xray-crystallography
python app.py
```

## Pipeline Steps

| Step | Engine | Description |
|---|---|---|
| **Import** | fabio | Read 12+ diffraction image formats (CBF, HDF5, SMV, TIFF, etc.) |
| **Find Spots** | DIALS / numpy | Detect diffraction spots via thresholding + local maxima |
| **Index** | DIALS / numpy | Assign Miller indices, determine unit cell and space group |
| **Integrate** | DIALS / numpy | Measure reflection intensities with I/σ statistics |
| **Scale** | DIALS / numpy | Cross-dataset scaling: R-merge, R-pim, CC½ |
| **Merge** | DIALS / reciprocalspaceship | Export merged MTZ with reflection data |
| **Mol. Replacement** | PHASER (PHENIX) | Solve structure by molecular replacement (LLG/TFZ scoring) |
| **Refinement** | phenix.refine | Structure refinement with R-work/R-free monitoring |
| **Validation** | MolProbity (PHENIX) | Ramachandran analysis, clash score, geometry validation |

All steps include numpy/scipy fallbacks — the full 9-step pipeline runs even without DIALS or PHENIX installed (producing estimated/placeholder results for testing).

## Architecture

```
xray-crystallography/
├── app.py                     # Flask entry point (port 5101)
├── src/
│   ├── image_import/          # Multi-format diffraction image reader
│   ├── spot_finding/          # Spot detection (DIALS + numpy fallback)
│   ├── indexing/              # Crystal lattice indexing
│   ├── integration/           # Reflection intensity integration
│   ├── scaling/               # Scaling + MTZ export
│   ├── structure_factors/     # I→F conversion, free R flags
│   ├── molecular_replacement/ # PHASER subprocess wrapper
│   ├── refinement/            # phenix.refine + MolProbity wrappers
│   ├── pipeline/              # Orchestrator, async task queue, state store
│   └── web/                   # Flask API routes (14 endpoints)
├── templates/index.html       # Single-page application UI
├── static/js/                 # Interactive components (image viewer, charts, Mol*)
└── data/                      # Job storage (SQLite + per-job directories)
```

### Key Design Decisions

- **Async task queue**: `ThreadPoolExecutor` + SQLite — no Redis/Celery dependency
- **Resource-aware scheduling**: Steps weighted as light/medium/heavy with concurrency limits
- **File-based data flow**: Each step reads/writes intermediate files in `data/jobs/<uuid>/`
- **Multi-tier PHENIX detection**: user config → env var → registry → glob scan → fallback

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/jobs` | Create a new job |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/<id>` | Get job status + pipeline state |
| DELETE | `/api/jobs/<id>` | Delete job and data |
| POST | `/api/jobs/<id>/upload` | Upload diffraction images |
| POST | `/api/jobs/<id>/steps/<step>` | Run a single pipeline step |
| POST | `/api/jobs/<id>/run` | Run full pipeline |
| GET | `/api/jobs/<id>/files/mtz` | Download merged MTZ |
| GET | `/api/jobs/<id>/files/pdb` | Download refined PDB |
| GET | `/api/system/dependencies` | Engine availability check |
| GET/POST | `/api/system/phenix-path` | View/set PHENIX installation path |

## Dependencies

### Required (pip)
- numpy, scipy, flask, matplotlib, pydantic

### Optional — for real crystallographic computation

| Engine | Install | Provides |
|---|---|---|
| fabio | `pip install fabio` | Multi-format image reading |
| DIALS | `conda install -c conda-forge dials` | Spot finding, indexing, integration, scaling |
| reciprocalspaceship | `pip install reciprocalspaceship` | MTZ I/O with pandas-like API |
| gemmi | `pip install gemmi` | PDB/CIF manipulation, symmetry |
| PHENIX | [phenix-online.org](https://phenix-online.org) | PHASER, phenix.refine, MolProbity |

### PHENIX Path Detection

PHENIX installation is auto-detected via a 6-tier chain:
1. User-specified path (web UI or `configure_phenix_path()`)
2. `PHENIX` / `PHENIX_ROOT` environment variable
3. Windows registry (`HKLM\SOFTWARE\Phenix\InstallPath`)
4. Filesystem glob scan (`D:\ProgramData\phenix-*`, `C:\phenix-*`)
5. Hardcoded fallback paths

Change the path at runtime:
```python
from src.pipeline.phenix_paths import configure_phenix_path
configure_phenix_path("D:/custom/phenix-2.1")
```
Or via API: `POST /api/system/phenix-path {"path": "D:/custom/phenix-2.1"}`

## Web Interface

The single-page app provides:
- **Job Dashboard**: create, select, delete jobs with status indicators
- **Pipeline Progress Bar**: 9-step visual flow with color-coded status (pending/running/completed/failed)
- **Diffraction Image Viewer**: Canvas-based 2D heatmap with zoom/pan, spot overlay, resolution rings
- **Statistics Charts**: I/σ, completeness, R-merge vs resolution bins
- **3D Model Viewer**: Embedded Mol* viewer for PDB structures
- **PHENIX Path Manager**: view/change PHENIX installation location

## Supported Image Formats

Via fabio: CBF, HDF5 (Eiger master.h5), SMV (ADSC/Rigaku), TIFF, EDF, MarCCD, Bruker, and more.

Without fabio: numpy `.npy` arrays for testing.

## License

MIT
