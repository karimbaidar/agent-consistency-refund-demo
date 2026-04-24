FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY refund_demo ./refund_demo
COPY samples ./samples
COPY assets ./assets
COPY LICENSE ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install -e .

ENV MODEL_PROVIDER=ollama
ENV OLLAMA_BASE_URL=http://ollama:11434
ENV OLLAMA_MODEL=qwen3:8b
ENV OUTPUT_DIR=/app/runs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "refund_demo.web:app", "--host", "0.0.0.0", "--port", "8000"]
