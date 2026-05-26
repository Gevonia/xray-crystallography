"""Extract beam, detector, and goniometer metadata from diffraction image headers."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CBF_KEYS = {
    "wavelength": ["Wavelength", "wavelength", "X-ray_wavelength"],
    "detector_distance": ["Detector_distance", "detector_distance"],
    "beam_center_x": ["Beam_xy", "BeamX", "Beam_x"],
    "beam_center_y": ["BeamY", "Beam_y"],
    "oscillation_start": ["Oscillation_axis", "Start_angle", "Phi"],
    "oscillation_range": ["Angle_increment", "Oscillation_range"],
    "exposure_time": ["Exposure_time", "Exposure_period", "Count_time"],
    "pixel_size_x": ["Pixel_size", "X_pixel_size"],
    "pixel_size_y": ["Y_pixel_size"],
    "detector_type": ["Detector_type", "Detector"],
    "two_theta": ["Two_theta", "Detector_2theta"],
}


def _search_header(header: dict, keys: list[str]) -> str | None:
    """Case-insensitive key search in a flat or nested header dict."""
    if not header:
        return None

    header_lower = {k.lower(): v for k, v in header.items()}
    for candidate in keys:
        val = header_lower.get(candidate.lower())
        if val is not None:
            return str(val)

    for k, v in header.items():
        if isinstance(v, dict):
            result = _search_header(v, keys)
            if result is not None:
                return result
    return None


def _parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        parts = raw.replace(",", " ").split()
        return float(parts[0]) if parts else None
    except (ValueError, IndexError):
        return None


def extract_metadata(fabio_image, filepath: Path) -> dict:
    """Extract crystallographic metadata from a fabio image object."""
    header = getattr(fabio_image, "header", None) or {}

    wavelength = _parse_float(_search_header(header, CBF_KEYS["wavelength"]))
    distance = _parse_float(_search_header(header, CBF_KEYS["detector_distance"]))
    beam_x = _parse_float(_search_header(header, CBF_KEYS["beam_center_x"]))
    beam_y = _parse_float(_search_header(header, CBF_KEYS["beam_center_y"]))
    osc_start = _parse_float(_search_header(header, CBF_KEYS["oscillation_start"]))
    osc_range = _parse_float(_search_header(header, CBF_KEYS["oscillation_range"]))
    exposure = _parse_float(_search_header(header, CBF_KEYS["exposure_time"]))
    px_x = _parse_float(_search_header(header, CBF_KEYS["pixel_size_x"]))
    px_y = _parse_float(_search_header(header, CBF_KEYS["pixel_size_y"]))
    detector = _search_header(header, CBF_KEYS["detector_type"])
    two_theta = _parse_float(_search_header(header, CBF_KEYS["two_theta"]))

    meta = {
        "wavelength": wavelength,
        "detector_distance_mm": distance,
        "beam_center": [beam_x, beam_y],
        "oscillation_start_deg": osc_start,
        "oscillation_range_deg": osc_range,
        "exposure_time_s": exposure,
        "pixel_size_mm": [px_x, px_y],
        "detector_type": detector,
        "two_theta_deg": two_theta,
        "filepath": str(filepath),
        "file_size_bytes": filepath.stat().st_size if filepath.exists() else None,
    }
    return {k: v for k, v in meta.items() if v is not None}
