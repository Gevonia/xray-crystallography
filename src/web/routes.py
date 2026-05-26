"""Flask Blueprint for all API routes."""
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

api_bp = Blueprint("api", __name__)


def _orchestrator():
    return current_app.config["orchestrator"]


# -- Job CRUD --

@api_bp.route("/jobs", methods=["POST"])
def create_job():
    data = request.get_json(silent=True) or {}
    job_id = _orchestrator().create_job(
        name=data.get("name", ""),
        params=data.get("params"),
    )
    return jsonify({"job_id": job_id})


@api_bp.route("/jobs", methods=["GET"])
def list_jobs():
    jobs = _orchestrator().list_jobs()
    return jsonify(jobs)


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = _orchestrator().get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@api_bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    _orchestrator().delete_job(job_id)
    return jsonify({"deleted": job_id})


# -- Image upload --

@api_bp.route("/jobs/<job_id>/upload", methods=["POST"])
def upload_images(job_id):
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    upload_dir = _orchestrator().config.data_root / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in request.files.getlist("files"):
        if f.filename:
            dest = upload_dir / f.filename
            f.save(str(dest))
            saved.append(dest)

    if not saved:
        return jsonify({"error": "No valid files"}), 400

    metas = _orchestrator().store_uploaded_images(job_id, saved)
    return jsonify({"count": len(metas), "images": metas})


# -- Pipeline step execution --

@api_bp.route("/jobs/<job_id>/steps/<step_name>", methods=["POST"])
def run_step(job_id, step_name):
    result = _orchestrator().run_step(job_id, step_name)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@api_bp.route("/jobs/<job_id>/run", methods=["POST"])
def run_full_pipeline(job_id):
    results = _orchestrator().run_full_pipeline(job_id)
    return jsonify({"steps": results})


# -- Step results --

@api_bp.route("/jobs/<job_id>/spots", methods=["GET"])
def get_spots(job_id):
    detail = _orchestrator().state_store.get_step_detail(job_id, "find-spots")
    if not detail:
        return jsonify({"error": "Spot finding not run"}), 404
    return jsonify(dict(detail))


@api_bp.route("/jobs/<job_id>/crystal", methods=["GET"])
def get_crystal(job_id):
    detail = _orchestrator().state_store.get_step_detail(job_id, "index")
    if not detail:
        return jsonify({"error": "Indexing not run"}), 404
    return jsonify(dict(detail))


@api_bp.route("/jobs/<job_id>/statistics", methods=["GET"])
def get_statistics(job_id):
    state = _orchestrator().state_store.get_job_state(job_id)
    stats = {}
    for step in ["integrate", "scale", "merge", "refine", "validate"]:
        d = _orchestrator().state_store.get_step_detail(job_id, step)
        stats[step] = {
            "status": state.get(step, "pending"),
            "result": d.get("result_json") if d else None,
        }
    return jsonify(stats)


# -- File downloads --


def _safe_send(path: Path, mimetype: str, download_name: str):
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(path), mimetype=mimetype, as_attachment=True,
                     download_name=download_name)


@api_bp.route("/jobs/<job_id>/files/mtz", methods=["GET"])
def download_mtz(job_id):
    mtz_path = _orchestrator()._job_dir(job_id) / "merge" / "merged.mtz"
    return _safe_send(mtz_path, "application/octet-stream", f"{job_id}_merged.mtz")


@api_bp.route("/jobs/<job_id>/files/pdb", methods=["GET"])
def download_pdb(job_id):
    pdb_path = _orchestrator()._job_dir(job_id) / "refine" / "refined.pdb"
    return _safe_send(pdb_path, "chemical/x-pdb", f"{job_id}_refined.pdb")


# -- Preview image (diffraction image as PNG) --

@api_bp.route("/jobs/<job_id>/preview", methods=["GET"])
def get_preview(job_id):
    job_dir = _orchestrator()._job_dir(job_id)
    images_dir = job_dir / "images"
    if not images_dir.exists():
        return jsonify({"error": "No images uploaded"}), 404
    try:
        import fabio
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return jsonify({"error": "fabio/matplotlib not installed"}), 500

    files = list(images_dir.iterdir())
    if not files:
        return jsonify({"error": "No images"}), 404

    img_path = files[0]
    try:
        fabio_img = fabio.open(str(img_path))
        data = fabio_img.data
    except Exception:
        return jsonify({"error": "Cannot read image"}), 500

    vmin, vmax = np.percentile(data, [1, 99])
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(data, cmap="gray", vmin=vmin, vmax=vmax, origin="lower")
    ax.set_title(img_path.name)
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# -- System routes --

@api_bp.route("/system/dependencies", methods=["GET"])
def system_dependencies():
    return jsonify(_orchestrator().get_system_status())


@api_bp.route("/system/config", methods=["GET"])
def system_config():
    return jsonify(_orchestrator().config.to_dict())


# -- PHENIX path management --

@api_bp.route("/system/phenix-path", methods=["GET"])
def get_phenix_path():
    from src.pipeline.phenix_paths import (
        get_resolved_path, get_detection_source, has_phenix, list_available_tools,
    )
    return jsonify({
        "resolved_path": get_resolved_path(),
        "detection_source": get_detection_source(),
        "available": has_phenix(),
        "tools_count": len(list_available_tools()),
    })


@api_bp.route("/system/phenix-path", methods=["POST"])
def set_phenix_path():
    from src.pipeline.phenix_paths import (
        configure_phenix_path, get_resolved_path, has_phenix,
    )
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    configure_phenix_path(path)
    return jsonify({
        "resolved_path": get_resolved_path(),
        "available": has_phenix(),
    })
