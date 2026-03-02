# Test Effort Estimation Tool — Multi-stage Docker build
# Builds Python backend + Streamlit frontend + NiceGUI frontend in a single image.
#
# Build:  docker build -t estimation-tool .
# Run:    docker run -p 8000:8000 -p 8501:8501 -p 8502:8502 estimation-tool
#
# Full rebuild (when base image or system deps change):
#   docker build --target base -t estimation-tool-base .
#   docker build -t estimation-tool .

# ── Stage 1: base — system deps + Python packages ────────────────
FROM i2j6hub1vt001.corp.idemia.com/library/python:3.12-slim AS base

# System dependencies required by some Python packages (e.g. cryptography, lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from the backend project, Streamlit, and NiceGUI.
# Copying only pyproject.toml / requirements.txt first lets Docker cache this
# layer when only application code changes.
COPY backend/pyproject.toml backend/
COPY frontend_nicegui/requirements.txt frontend_nicegui/
RUN mkdir -p backend/src && touch backend/src/__init__.py \
    && pip install --no-cache-dir ./backend streamlit \
    && pip install --no-cache-dir -r frontend_nicegui/requirements.txt

# ── Stage 2: app — source code + runtime config ──────────────────
FROM base AS app

WORKDIR /app

# Copy application source after dependencies are installed to maximise cache hits.
COPY backend/ ./backend/
COPY frontend_web/ ./frontend_web/
COPY frontend_nicegui/ ./frontend_nicegui/
COPY data/seed_data.json ./data/

# Ensure the runtime data directory exists (SQLite file is written here).
RUN mkdir -p /app/data

# Copy Streamlit config
COPY .streamlit/ ./.streamlit/

# Default API_URL for frontends to reach the backend inside the container.
ENV API_URL=http://localhost:8000/api

# Entrypoint: starts FastAPI backend, Streamlit frontend, and NiceGUI frontend
# concurrently. The script uses "wait -n" to exit as soon as any process dies,
# which allows Docker to detect failures and restart the container when
# restart: unless-stopped is configured.
RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -e' \
    '' \
    'echo "Starting Test Effort Estimation Tool..."' \
    '' \
    '# Start FastAPI backend' \
    'cd /app/backend' \
    'uvicorn src.api.app:app --host 0.0.0.0 --port 8000 &' \
    'BACKEND_PID=$!' \
    '' \
    '# Start Streamlit frontend' \
    'cd /app' \
    'streamlit run frontend_web/app.py \' \
    '    --server.port 8501 \' \
    '    --server.address 0.0.0.0 \' \
    '    --server.headless true \' \
    '    --browser.gatherUsageStats false &' \
    'STREAMLIT_PID=$!' \
    '' \
    '# Start NiceGUI frontend' \
    'cd /app' \
    'python frontend_nicegui/app.py &' \
    'NICEGUI_PID=$!' \
    '' \
    '# Exit when any process terminates' \
    'wait -n $BACKEND_PID $STREAMLIT_PID $NICEGUI_PID' \
    'exit $?' \
    > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# FastAPI REST API
EXPOSE 8000
# Streamlit web UI
EXPOSE 8501
# NiceGUI web UI (recommended)
EXPOSE 8502

# Lightweight health check against the unauthenticated healthcheck endpoint.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/healthcheck')" \
        || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
