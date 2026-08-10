# ============================================================
# MedDeviceAgent Dockerfile
# 医疗设备智能语音客服 Agent 平台
# ============================================================

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="MedDeviceAgent"
LABEL org.opencontainers.image.description="医疗设备智能语音客服 Agent 平台"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r svagent && useradd -r -g svagent -d /app svagent

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY --chown=svagent:svagent . .

USER svagent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
