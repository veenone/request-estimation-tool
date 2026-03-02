# Test Effort Estimation Tool — Multi-stage Docker build
# Builds Python backend + Streamlit frontend in a single image.
#
# Build:  docker build -t estimation-tool .
# Run:    docker run -p 8000:8000 -p 8501:8501 estimation-tool

FROM python:3.12-slim AS base

# System dependencies required by some Python packages (e.g. cryptography, lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from the backend project and Streamlit separately.
# Copying only pyproject.toml first lets Docker cache this layer when only
# application code changes.
COPY backend/pyproject.toml backend/
RUN pip install --no-cache-dir ./backend streamlit

# Copy application source after dependencies are installed to maximise cache hits.
COPY backend/ ./backend/
COPY frontend_web/ ./frontend_web/
COPY data/seed_data.json ./data/

# Ensure the runtime data directory exists (SQLite file is written here).
RUN mkdir -p /app/data

# Copy Streamlit config
COPY .streamlit/ ./.streamlit/

# Entrypoint: starts FastAPI backend and Streamlit frontend concurrently.
# SSL/TLS is enabled when SSL_CERTFILE and SSL_KEYFILE env vars are set.
# The script uses "wait -n" to exit as soon as either process dies, which
# allows Docker to detect failures and restart the container when
# restart: unless-stopped is configured.
RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -e' \
    '' \
    'echo "Starting Test Effort Estimation Tool..."' \
    '' \
    '# Build SSL args if cert files are provided' \
    'UVICORN_SSL_ARGS=""' \
    'STREAMLIT_SSL_ARGS=""' \
    'if [ -n "$SSL_CERTFILE" ] && [ -n "$SSL_KEYFILE" ]; then' \
    '    echo "TLS enabled: $SSL_CERTFILE / $SSL_KEYFILE"' \
    '    UVICORN_SSL_ARGS="--ssl-certfile $SSL_CERTFILE --ssl-keyfile $SSL_KEYFILE"' \
    '    STREAMLIT_SSL_ARGS="--server.sslCertFile $SSL_CERTFILE --server.sslKeyFile $SSL_KEYFILE"' \
    'fi' \
    '' \
    '# Start FastAPI backend' \
    'cd /app/backend' \
    'uvicorn src.api.app:app --host 0.0.0.0 --port 8000 $UVICORN_SSL_ARGS &' \
    'BACKEND_PID=$!' \
    '' \
    '# Start Streamlit frontend' \
    'cd /app' \
    'streamlit run frontend_web/app.py \' \
    '    --server.port 8501 \' \
    '    --server.address 0.0.0.0 \' \
    '    --server.headless true \' \
    '    --browser.gatherUsageStats false \' \
    '    $STREAMLIT_SSL_ARGS &' \
    'FRONTEND_PID=$!' \
    '' \
    '# Exit when either process terminates' \
    'wait -n $BACKEND_PID $FRONTEND_PID' \
    'exit $?' \
    > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# FastAPI REST API
EXPOSE 8000
# Streamlit web UI
EXPOSE 8501

# Lightweight health check against the FastAPI features endpoint.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/features')" \
        || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
