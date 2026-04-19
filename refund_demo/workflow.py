import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_consistency import ConsistencyError, JsonlReceiptStore, WorkflowRun

from .agents import CommsAgent, IntakeAgent, PolicyAgent, RefundAgent, RiskAgent
from .config import AppConfig
from .providers import ModelProvider
from .services import EmailGateway, RefundGateway


@dataclass
class WorkflowResult:
    run_id: str
    status: str
    run_dir: Path
    report_path: Path
    receipts_path: Path
    receipts: List[Dict[str, Any]]
    final_message: Optional[Dict[str, Any]] = None
    failure: Optional[Dict[str, str]] = None


def load_case(path: str) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_refund_workflow(
    case: Dict[str, Any],
    *,
    config: AppConfig,
    provider: ModelProvider,
) -> WorkflowResult:
    run_id = case.get("run_id") or case["request"]["ticket_id"]
    run_dir = Path(config.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = run_dir / "receipts.jsonl"
    report_path = run_dir / "summary.json"
    if receipts_path.exists():
        receipts_path.unlink()

    store = JsonlReceiptStore(str(receipts_path))
    run = WorkflowRun(run_id, store=store, on_violation=config.consistency_on_violation)
    refund_gateway = RefundGateway(
        refund_status=case.get("provider", {}).get("refund_status", "settled")
    )
    email_gateway = EmailGateway()

    final_message = None
    failure = None

    try:
        intake_packet = IntakeAgent().run(run, provider, case)
        policy_packet = PolicyAgent().run(run, case, intake_packet)
        risk_packet = RiskAgent().run(run, case, policy_packet)
        refund_packet = RefundAgent(refund_gateway).run(run, risk_packet)
        final_message = CommsAgent(email_gateway).run(run, provider, refund_packet)
        status = "passed"
    except (ConsistencyError, Exception) as exc:
        status = "failed"
        failure = {"type": exc.__class__.__name__, "message": str(exc)}

    receipts = [receipt.to_dict() for receipt in run.receipts()]
    report = {
        "run_id": run_id,
        "status": status,
        "provider": provider.name,
        "scenario": case.get("scenario", "custom"),
        "failure": failure,
        "final_message": final_message,
        "receipt_count": len(receipts),
        "receipts": receipts,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return WorkflowResult(
        run_id=run_id,
        status=status,
        run_dir=run_dir,
        report_path=report_path,
        receipts_path=receipts_path,
        receipts=receipts,
        final_message=final_message,
        failure=failure,
    )
