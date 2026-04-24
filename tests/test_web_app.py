from pathlib import Path

from fastapi.testclient import TestClient

from refund_demo.config import AppConfig
from refund_demo.web import ORCHESTRATION_PATTERN, create_app


def _client(tmp_path):
    config = AppConfig(output_dir=str(tmp_path), consistency_on_violation="raise")
    return TestClient(create_app(config))


def test_web_app_serves_frontend(tmp_path):
    client = _client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Refund Consistency Lab" in response.text


def test_web_api_lists_scenarios_and_pattern(tmp_path):
    client = _client(tmp_path)

    config = client.get("/api/config").json()
    scenarios = client.get("/api/scenarios").json()

    assert config["orchestration_pattern"] == ORCHESTRATION_PATTERN
    assert {scenario["id"] for scenario in scenarios} == {
        "happy_path",
        "stale_policy",
        "missing_handoff",
        "pending_refund",
    }


def test_web_api_runs_happy_path_with_heuristic_provider(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/runs",
        json={"scenario": "happy_path", "provider": "heuristic"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["receipt_count"] == 5
    assert payload["orchestration_pattern"] == ORCHESTRATION_PATTERN
    assert payload["links"]["html_report"] == "/runs/demo-happy-refund/report.html"
    assert (Path(tmp_path) / "demo-happy-refund" / "report.html").exists()


def test_web_api_rejects_unknown_scenario(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/runs", json={"scenario": "unknown"})

    assert response.status_code == 404
