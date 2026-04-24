import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class AppConfig:
    model_provider: str = "heuristic"
    model_name: str = "refund-demo-local"
    model_base_url: str = ""
    model_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    consistency_on_violation: str = "raise"
    output_dir: str = "runs"

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "AppConfig":
        source = env if env is not None else os.environ
        provider = source.get("MODEL_PROVIDER", "heuristic").strip().lower()
        return cls(
            model_provider=provider,
            model_name=source.get("MODEL_NAME", "refund-demo-local"),
            model_base_url=source.get("MODEL_BASE_URL", ""),
            model_api_key=source.get("MODEL_API_KEY", ""),
            ollama_base_url=source.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=source.get("OLLAMA_MODEL", "qwen3:8b"),
            consistency_on_violation=source.get("CONSISTENCY_ON_VIOLATION", "raise"),
            output_dir=source.get("OUTPUT_DIR", "runs"),
        )
