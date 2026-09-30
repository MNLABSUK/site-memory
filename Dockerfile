# Site Memory public demo image (Render / Hugging Face Spaces / any Docker host).
# Secrets (NEBIUS_API_KEY, optional TAVILY_API_KEY) come from the host's secret env, never from this repo.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Europe/London \
    SITE_MEMORY_DEMO=1 SITE_MEMORY_DATA_DIR=/tmp/site-memory-data \
    NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1 \
    NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B \
    NEBIUS_NIGHTLY_MODEL=nvidia/nemotron-3-super-120b-a12b \
    NEBIUS_SKILLS_MODEL=nvidia/nemotron-3-super-120b-a12b
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY site_memory ./site_memory
COPY web ./web
RUN useradd -m -u 1000 app && chown -R app /app
USER app
EXPOSE 7860
CMD ["sh", "-c", "uvicorn site_memory.app:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
