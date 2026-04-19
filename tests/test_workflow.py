import json
from pathlib import Path

from refund_demo.config import AppConfig
from refund_demo.providers import HeuristicProvider
from refund_demo.workflow import load_case, run_refund_workflow

ROOT = Path(__file__).resolve().parents[1]


def _config(tmp_path):
    return AppConfig(output_dir=str(tmp_path), consistency_on_violation="raise")


def test_happy_path_produces_five_passing_receipts(tmp_path):
    case = load_case(str(ROOT / "samples/inputs/happy_path.json"))

    result = run_refund_workflow(case, config=_config(tmp_path), provider=HeuristicProvider())

    assert result.status == "passed"
    assert len(result.receipts) == 5
    assert [receipt["status"] for receipt in result.receipts] == ["passed"] * 5
    assert result.final_message["status"] == "sent"


def test_stale_policy_fails_with_stale_state_issue(tmp_path):
    case = load_case(str(ROOT / "samples/inputs/stale_policy.json"))

    result = run_refund_workflow(case, config=_config(tmp_path), provider=HeuristicProvider())

    assert result.status == "failed"
    assert result.failure["type"] == "StaleStateError"
    assert any(
        issue["code"] == "stale_state"
        for receipt in result.receipts
        for issue in receipt["issues"]
    )


def test_missing_handoff_fails_before_policy_agent_runs(tmp_path):
    case = load_case(str(ROOT / "samples/inputs/missing_handoff.json"))

    result = run_refund_workflow(case, config=_config(tmp_path), provider=HeuristicProvider())

    assert result.status == "failed"
    assert result.failure["type"] == "HandoffValidationError"
    assert len(result.receipts) == 1
    assert result.receipts[0]["issues"][0]["code"] == "invalid_handoff"


def test_pending_refund_catches_false_success(tmp_path):
    case = load_case(str(ROOT / "samples/inputs/pending_refund.json"))

    result = run_refund_workflow(case, config=_config(tmp_path), provider=HeuristicProvider())

    assert result.status == "failed"
    assert result.failure["type"] == "OutcomeVerificationError"
    refund_receipt = result.receipts[-1]
    assert refund_receipt["step_id"] == "04-refund"
    assert refund_receipt["outcomes"][0]["passed"] is False


def test_report_file_contains_receipts(tmp_path):
    case = load_case(str(ROOT / "samples/inputs/happy_path.json"))

    result = run_refund_workflow(case, config=_config(tmp_path), provider=HeuristicProvider())
    report = json.loads(result.report_path.read_text(encoding="utf-8"))

    assert report["status"] == "passed"
    assert report["receipt_count"] == 5
    assert report["receipts"][0]["agent"] == "intake-agent"
