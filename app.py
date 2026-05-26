"""X-ray Crystallography Pipeline — Flask web application."""
from pathlib import Path

from flask import Flask, render_template

from src.pipeline.config import PipelineConfig
from src.pipeline.orchestrator import PipelineOrchestrator
from src.web.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB
    app.config["orchestrator"] = PipelineOrchestrator(config=PipelineConfig())
    app.register_blueprint(api_bp, url_prefix="/api")
    return app


app = create_app()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/jobs/<job_id>")
def job_detail(job_id):
    return render_template("index.html", job_id=job_id)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5101)
