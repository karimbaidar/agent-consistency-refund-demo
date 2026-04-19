import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict


def stable_key(prefix: str, payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"


@dataclass
class RefundGateway:
    refund_status: str = "settled"
    issued: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def issue_refund(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        key = stable_key("refund", intent)
        if key not in self.issued:
            self.issued[key] = {
                "refund_id": key,
                "status": self.refund_status,
                "order_id": intent["order_id"],
                "amount": intent["amount"],
                "currency": intent["currency"],
            }
        return self.issued[key]

    def get_refund(self, refund_id: str) -> Dict[str, Any]:
        return self.issued[refund_id]


@dataclass
class EmailGateway:
    sent: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def send_email(self, customer_id: str, body: str) -> Dict[str, Any]:
        message_id = stable_key("email", {"customer_id": customer_id, "body": body})
        self.sent[message_id] = {
            "message_id": message_id,
            "customer_id": customer_id,
            "body": body,
            "status": "sent",
        }
        return self.sent[message_id]

    def get_message(self, message_id: str) -> Dict[str, Any]:
        return self.sent[message_id]
