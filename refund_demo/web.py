import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config import AppConfig, load_dotenv
from .providers import build_provider
from .workflow import load_case, run_refund_workflow

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples" / "inputs"
STATIC_DIR = Path(__file__).resolve().parent / "static"

ORCHESTRATION_PATTERN = "sequential receipt-gated handoff pipeline"

SCENARIOS: Dict[str, Dict[str, str]] = {
    "happy_path": {
        "file": "happy_path.json",
        "name": "Happy refund",
        "expected": "passed",
        "description": "All agents complete with verified handoffs, artifacts, and outcomes.",
    },
    "stale_policy": {
        "file": "stale_policy.json",
        "name": "Stale policy",
        "expected": "failed",
        "description": "Policy snapshot drift stops the workflow before payment execution.",
    },
    "missing_handoff": {
        "file": "missing_handoff.json",
        "name": "Missing handoff fact",
        "expected": "failed",
        "description": "A required handoff fact is absent, so the next agent cannot continue.",
    },
    "pending_refund": {
        "file": "pending_refund.json",
        "name": "Pending refund",
        "expected": "failed",
        "description": "The provider returns pending, so false success is rejected.",
    },
}


class RunRequest(BaseModel):
    scenario: str = "happy_path"
    provider: Optional[str] = None


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    load_dotenv()
    base_config = config or AppConfig.from_env()
    runs_dir = Path(base_config.output_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Agent Consistency Refund Demo",
        version=__version__,
        description="Visual refund workflow demo for agent-consistency receipts.",
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "provider": base_config.model_provider}

    @app.get("/api/config")
    def current_config() -> Dict[str, str]:
        return {
            "default_provider": base_config.model_provider,
            "ollama_model": base_config.ollama_model,
            "ollama_base_url": base_config.ollama_base_url,
            "orchestration_pattern": ORCHESTRATION_PATTERN,
        }

    @app.get("/api/scenarios")
    def scenarios() -> List[Dict[str, str]]:
        return [{"id": key, **value} for key, value in SCENARIOS.items()]

    @app.post("/api/runs")
    def run_scenario(request: RunRequest) -> Dict[str, Any]:
        scenario = SCENARIOS.get(request.scenario)
        if scenario is None:
            raise HTTPException(status_code=404, detail=f"unknown scenario '{request.scenario}'")

        provider_name = request.provider or base_config.model_provider
        run_config = replace(base_config, model_provider=provider_name)
        try:
            provider = build_provider(run_config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        case = load_case(str(SAMPLES_DIR / scenario["file"]))
        result = run_refund_workflow(case, config=run_config, provider=provider)
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        report["orchestration_pattern"] = ORCHESTRATION_PATTERN
        report["links"] = {
            "summary": f"/runs/{result.run_id}/summary.json",
            "html_report": f"/runs/{result.run_id}/report.html",
            "receipts": f"/runs/{result.run_id}/receipts.jsonl",
        }
        return report

    return app


app = create_app()
