"""Multi-format diffraction image reader via fabio."""
import json
import logging
from pathlib import Path

import numpy as np

from .metadata import extract_metadata

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".cbf", ".img", ".h5", ".tif", ".tiff",
    ".edf", ".mar120", ".mar2300", ".mar3450", ".sfrm",
    ".mccd", ".npy",
}


def read_image(path: str | Path) -> tuple[np.ndarray, dict]:
    """Read a single diffraction image, return (data_array, metadata_dict)."""
    import fabio

    path = Path(path)
    img = fabio.open(str(path))
    data = img.data.astype(np.float64)
    meta = extract_metadata(img, path)
    meta["format"] = img.__class__.__name__
    meta["shape"] = list(data.shape)
    meta["dtype"] = str(data.dtype)
    return data, meta


def import_images(file_paths: list[str | Path], output_dir: str | Path) -> dict:
    """Read all images, write summary, return import result dict.

    Writes:
      output_dir/images_meta.json  — per-image metadata
      output_dir/imported.npy      — stacked data for single-frame images
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_meta = []
    all_data = []

    for fp in file_paths:
        fp = Path(fp)
        if fp.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.warning("Skipping unsupported format: %s", fp.suffix)
            continue
        try:
            data, meta = read_image(fp)
            all_meta.append({"filename": fp.name, **meta})
            all_data.append(data)
        except Exception:
            logger.exception("Failed to read %s", fp.name)
            all_meta.append({"filename": fp.name, "error": "read failed"})

    if not all_meta:
        raise RuntimeError("No images were successfully read")

    # Write metadata
    with open(output_dir / "images_meta.json", "w") as f:
        json.dump(all_meta, f, indent=2, default=str)

    # Stack data for single-frame images
    if all_data:
        stacked = np.stack(all_data) if len(all_data) > 1 else all_data[0]
        np.save(str(output_dir / "imported.npy"), stacked)

    n_images = len(all_meta)
    format_counts = {}
    for m in all_meta:
        fmt = m.get("format", "unknown")
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    return {
        "n_images": n_images,
        "formats": format_counts,
        "metadata": all_meta,
        "output_files": [
            str(output_dir / "images_meta.json"),
            str(output_dir / "imported.npy"),
        ],
    }
