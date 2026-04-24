from agent_consistency import HandoffContract, VerifierRegistry

INTAKE_TO_POLICY = HandoffContract.define(
    "intake_to_policy",
    required_facts=[
        "ticket_id",
        "request.order_id",
        "request.amount",
        "request.reason",
        "order.id",
        "order.customer_id",
        "order.previous_refund_count",
    ],
    required_evidence=["order.previous_refund_count"],
    produced_artifacts=["request_extraction"],
)

POLICY_TO_RISK = HandoffContract.define(
    "policy_to_risk",
    required_facts=["request.order_id", "order.customer_id", "decision.eligible"],
    required_evidence=["policy"],
    produced_artifacts=["policy_decision"],
)

RISK_TO_REFUND = HandoffContract.define(
    "risk_to_refund",
    required_facts=[
        "request.order_id",
        "request.amount",
        "order.currency",
        "decision.eligible",
        "risk.approved",
    ],
    produced_artifacts=["risk_decision"],
    verifier="refund_intent_gate",
)

REFUND_TO_COMMS = HandoffContract.define(
    "refund_to_comms",
    required_facts=["customer_id", "order_id", "refund.refund_id", "refund.status"],
    required_evidence=["refund.status"],
    produced_artifacts=["refund_provider_status"],
    verifier="settled_refund_claim",
)


def build_verifier_registry() -> VerifierRegistry:
    registry = VerifierRegistry()

    @registry.register("refund_intent_gate")
    def refund_intent_gate(context):
        facts = context.facts or {}
        amount = facts["request"]["amount"]
        decision = facts["decision"]
        risk = facts["risk"]
        return amount < 500 and decision["eligible"] and risk["approved"]

    @registry.register("settled_refund_claim")
    def settled_refund_claim(context):
        facts = context.facts or {}
        return facts["refund"]["status"] == "settled"

    return registry
