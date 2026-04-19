import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict

from .config import AppConfig


class ModelProvider:
    name = "base"

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        raise NotImplementedError


class HeuristicProvider(ModelProvider):
    name = "heuristic"

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        lower = f"{system}\n{user}".lower()
        if json_mode:
            return json.dumps(
                {
                    "intent": "refund_request",
                    "reason": _pick_reason(lower),
                    "urgency": "normal",
                    "summary": "Customer is requesting a refund.",
                }
            )
        if "customer email" in lower or "customer message" in lower:
            return (
                "Hi, your refund has been approved and settled. "
                "We appreciate your patience and have recorded the refund on your order."
            )
        return "The workflow completed with consistent state, handoff, and outcome evidence."


@dataclass
class OpenAICompatibleProvider(ModelProvider):
    base_url: str
    api_key: str
    model: str
    name: str = "openai-compatible"

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = _post_json(
            f"{self.base_url.rstrip('/')}/chat/completions",
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
        )
        return response["choices"][0]["message"]["content"]


@dataclass
class OllamaProvider(ModelProvider):
    base_url: str
    model: str
    name: str = "ollama"

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        response = _post_json(f"{self.base_url.rstrip('/')}/api/chat", payload, headers={})
        return response["message"]["content"]


def build_provider(config: AppConfig) -> ModelProvider:
    if config.model_provider == "heuristic":
        return HeuristicProvider()
    if config.model_provider == "openai-compatible":
        return OpenAICompatibleProvider(
            base_url=config.model_base_url,
            api_key=config.model_api_key,
            model=config.model_name,
        )
    if config.model_provider == "ollama":
        return OllamaProvider(base_url=config.ollama_base_url, model=config.ollama_model)
    raise ValueError(f"unsupported MODEL_PROVIDER '{config.model_provider}'")


def _post_json(url: str, payload: Dict[str, Any], *, headers: Dict[str, str]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"model provider returned HTTP {exc.code}: {message}") from exc


def _pick_reason(text: str) -> str:
    for reason in ("damaged item", "wrong item", "not received"):
        if reason in text:
            return reason
    if "damaged" in text:
        return "damaged item"
    if "wrong" in text:
        return "wrong item"
    return "customer requested refund"
