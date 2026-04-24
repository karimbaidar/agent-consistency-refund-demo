from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_documents_local_llm_stack():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ollama/ollama" in compose
    assert "qwen3:8b" in compose
    assert "MODEL_PROVIDER" in compose
    assert "8000:8000" in compose


def test_dockerfile_runs_the_visual_app():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "refund_demo.web:app" in dockerfile
    assert "OLLAMA_BASE_URL=http://ollama:11434" in dockerfile
    assert "python -m pip install -e ." in dockerfile
