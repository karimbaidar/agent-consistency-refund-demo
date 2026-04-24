import json
from typing import Any, Dict

from agent_consistency import HandoffPacket, VerifierRegistry, WorkflowRun

from .contracts import INTAKE_TO_POLICY, POLICY_TO_RISK, REFUND_TO_COMMS, RISK_TO_REFUND
from .providers import ModelProvider
from .services import EmailGateway, RefundGateway


class IntakeAgent:
    name = "intake-agent"

    def run(
        self,
        run: WorkflowRun,
        provider: ModelProvider,
        case: Dict[str, Any],
    ) -> HandoffPacket:
        request = case["request"]
        order = case["order"]
        demo = case.get("demo", {})

        with run.step(
            self.name,
            "extract_refund_request",
            step_id="01-intake",
            assumptions=["support ticket and order record refer to the same customer"],
        ) as step:
            request_snapshot = step.read_state(
                "support_ticket",
                request,
                version=request["ticket_id"],
            )
            order_snapshot = step.read_state("order", order, version=order["version"])
            extraction = json.loads(
                provider.complete(
                    system=(
                        "Extract a compact refund request JSON object. "
                        "Return JSON only with keys intent, reason, urgency, summary. "
                        "The reason must be one of: damaged item, wrong item, not received."
                    ),
                    user=json.dumps({"request": request, "order": order}, sort_keys=True),
                    json_mode=True,
                )
            )
            if "reason" not in extraction:
                extraction["reason"] = _pick_allowed_reason(request["customer_message"])
            elif extraction["reason"] not in case["policy"]["allowed_reasons"]:
                extraction["reason"] = _pick_allowed_reason(request["customer_message"])
            extraction_artifact = step.proof_artifact(
                "request_extraction",
                extraction,
                kind="model_output",
                verified=True,
                verifier="json_parse",
            )

            order_facts = {
                "id": order["id"],
                "version": order["version"],
                "customer_id": order["customer_id"],
                "total": order["total"],
                "currency": order["currency"],
                "status": order["status"],
            }
            if not demo.get("omit_previous_refund_count"):
                order_facts["previous_refund_count"] = order["previous_refund_count"]

            return step.handoff(
                to_agent="policy-agent",
                task="decide whether the refund is policy-eligible",
                facts={
                    "ticket_id": request["ticket_id"],
                    "request": {
                        "order_id": request["order_id"],
                        "amount": request["requested_amount"],
                        "reason": extraction["reason"],
                    },
                    "order": order_facts,
                },
                evidence={
                    "support_ticket": request_snapshot.to_dict(),
                    "order.previous_refund_count": order_snapshot.to_dict(),
                },
                constraints=["do not refund when previous_refund_count exceeds policy"],
                artifacts=[extraction_artifact],
                contract=INTAKE_TO_POLICY,
            )


class PolicyAgent:
    name = "policy-agent"

    def run(self, run: WorkflowRun, case: Dict[str, Any], packet: HandoffPacket) -> HandoffPacket:
        policy = case["policy"]

        with run.step(
            self.name,
            "evaluate_policy",
            step_id="02-policy",
            assumptions=["policy version must be current before approving a refund"],
        ) as step:
            step.consume_handoff(packet, contract=INTAKE_TO_POLICY)
            policy_snapshot = step.read_state("refund_policy", policy, version=policy["version"])
            step.ensure_fresh(policy_snapshot, current_version=case["latest_policy_version"])

            request = packet.facts["request"]
            order = packet.facts["order"]
            reasons = []
            if request["amount"] > policy["max_refund_amount"]:
                reasons.append("requested amount exceeds policy limit")
            if order["previous_refund_count"] > policy["max_previous_refunds"]:
                reasons.append("customer already reached refund limit")
            if request["reason"] not in policy["allowed_reasons"]:
                reasons.append("refund reason is not policy-approved")

            decision = {
                "eligible": not reasons,
                "reasons": reasons or ["policy checks passed"],
                "policy_version": policy["version"],
            }
            step.write_state("policy_decision", decision, based_on=policy_snapshot)
            decision_artifact = step.proof_artifact(
                "policy_decision",
                decision,
                kind="decision",
                verified=decision["eligible"],
                verifier="policy_rules",
            )

            return step.handoff(
                to_agent="risk-agent",
                task="check customer risk before refund execution",
                facts={
                    "request": request,
                    "order": order,
                    "decision": decision,
                },
                evidence={"policy": policy_snapshot.to_dict()},
                artifacts=[decision_artifact],
                contract=POLICY_TO_RISK,
            )


class RiskAgent:
    name = "risk-agent"

    def run(self, run: WorkflowRun, case: Dict[str, Any], packet: HandoffPacket) -> HandoffPacket:
        risk = case["risk_profile"]

        with run.step(
            self.name,
            "assess_customer_risk",
            step_id="03-risk",
            assumptions=["risk profile version must be current before payment action"],
        ) as step:
            step.consume_handoff(packet, contract=POLICY_TO_RISK)
            risk_snapshot = step.read_state("risk_profile", risk, version=risk["version"])
            step.ensure_fresh(
                risk_snapshot,
                current_version=case.get("latest_risk_version", risk["version"]),
            )
            risk_approved = (
                risk["chargebacks_12m"] == 0
                and risk["manual_review"] is False
                and risk["account_age_days"] >= 30
            )
            risk_result = {
                "approved": risk_approved,
                "risk_version": risk["version"],
                "reason": "risk checks passed" if risk_approved else "manual review required",
            }
            step.write_state("risk_decision", risk_result, based_on=risk_snapshot)
            risk_artifact = step.proof_artifact(
                "risk_decision",
                risk_result,
                kind="decision",
                verified=risk_result["approved"],
                verifier="risk_rules",
            )

            return step.handoff(
                to_agent="refund-agent",
                task="issue refund only when policy and risk both approve",
                facts={
                    **packet.facts,
                    "risk": risk_result,
                },
                evidence={"risk_profile": risk_snapshot.to_dict(), **packet.evidence},
                constraints=["use a deterministic refund intent key"],
                artifacts=[risk_artifact],
                contract=RISK_TO_REFUND,
            )


class RefundAgent:
    name = "refund-agent"

    def __init__(self, gateway: RefundGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        run: WorkflowRun,
        packet: HandoffPacket,
        registry: VerifierRegistry,
    ) -> HandoffPacket:
        with run.step(
            self.name,
            "issue_refund",
            step_id="04-refund",
            assumptions=["payment provider status is authoritative for refund completion"],
        ) as step:
            step.consume_handoff(packet, contract=RISK_TO_REFUND, registry=registry)
            decision = packet.facts["decision"]
            risk = packet.facts["risk"]
            if not decision["eligible"] or not risk["approved"]:
                raise ValueError("refund cannot be issued without policy and risk approval")

            intent = {
                "order_id": packet.facts["request"]["order_id"],
                "amount": packet.facts["request"]["amount"],
                "currency": packet.facts["order"]["currency"],
                "policy_version": decision["policy_version"],
                "risk_version": risk["risk_version"],
            }
            refund = self.gateway.issue_refund(intent)
            step.write_state("refund", refund, version=refund["refund_id"], include_value=True)
            step.verify_outcome(
                "refund_settled",
                lambda: self.gateway.get_refund(refund["refund_id"])["status"] == "settled",
                failure_reason=f"refund status is {refund['status']}, not settled",
                details=refund,
            )
            refund_artifact = step.proof_artifact(
                "refund_provider_status",
                refund,
                kind="api_read",
                verified=refund["status"] == "settled",
                verifier="refund_settled",
                uri=f"provider://refunds/{refund['refund_id']}",
            )

            return step.handoff(
                to_agent="comms-agent",
                task="notify customer with evidence-backed refund status",
                facts={
                    "customer_id": packet.facts["order"]["customer_id"],
                    "order_id": packet.facts["request"]["order_id"],
                    "refund": refund,
                },
                evidence={"refund.status": refund, **packet.evidence},
                artifacts=[refund_artifact],
                contract=REFUND_TO_COMMS,
            )


class CommsAgent:
    name = "comms-agent"

    def __init__(self, gateway: EmailGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        run: WorkflowRun,
        provider: ModelProvider,
        packet: HandoffPacket,
        registry: VerifierRegistry,
    ) -> Dict[str, Any]:
        with run.step(
            self.name,
            "send_customer_message",
            step_id="05-comms",
            assumptions=["customer message must not claim more than refund evidence supports"],
        ) as step:
            step.consume_handoff(packet, contract=REFUND_TO_COMMS, registry=registry)
            step.require_supported_claims(
                packet,
                {"refund_complete": True},
                by=["refund.status"],
            )
            body = provider.complete(
                system="Write a concise customer email. Do not invent unsupported claims.",
                user=(
                    "Customer message for refund packet: "
                    f"{json.dumps(packet.facts, sort_keys=True)}"
                ),
            )
            message = self.gateway.send_email(packet.facts["customer_id"], body)
            step.write_state("customer_email", message, version=message["message_id"])
            step.verify_outcome(
                "email_sent",
                lambda: self.gateway.get_message(message["message_id"])["status"] == "sent",
                details={"message_id": message["message_id"]},
            )
            return message


def _pick_allowed_reason(text: str) -> str:
    lower = text.lower()
    if "wrong" in lower:
        return "wrong item"
    if "not received" in lower or "missing" in lower:
        return "not received"
    return "damaged item"
