"""FastAPI application setup."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from ..auth.middleware import AuthContextMiddleware
from ..database.engine import get_engine as _get_engine
from ..database.migrations import init_database

engine = _get_engine()
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:  # type: ignore[misc]
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_database()
    yield


app = FastAPI(
    title="Test Effort Estimation Tool",
    version="3.0.0",
    description="API for managing test effort estimations",
    lifespan=lifespan,
)

# Auth context middleware (extracts client IP for audit logging)
app.add_middleware(AuthContextMiddleware)

# CORS — restrict origins in production via CORS_ORIGINS env var
_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Import and include routes
from .routes import router  # noqa: E402

app.include_router(router, prefix="/api")


# ── Health / host-config endpoints (no auth required) ─────────────
# ── Streamlit _stcore requests (silently absorb) ──────────────────
# When both Streamlit and FastAPI run behind the same origin/proxy,
# Streamlit's JS client polls /_stcore/health and /_stcore/host-config
# on every page. Return 200 so these don't flood the log with 404s.

@app.get("/_stcore/health")
@app.get("/_stcore/host-config")
@app.get("/{path:path}/_stcore/health")
@app.get("/{path:path}/_stcore/host-config")
def _stcore_stub(path: str = ""):
    return {"status": "ok"}


@app.get("/api/healthcheck")
def healthcheck():
    """Simple liveness probe — returns 200 if the service is running."""
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/host-config")
def host_config():
    """Return runtime configuration useful for frontends."""
    return {
        "api_version": "3.0.0",
        "auth_providers": ["local", "ldap", "oidc"],
        "title": "Test Effort Estimation Tool",
    }
