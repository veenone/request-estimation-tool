"""FastAPI application setup."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..database.migrations import DEFAULT_DB_PATH, init_database

engine = create_engine(f"sqlite:///{DEFAULT_DB_PATH}", echo=False)
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
    version="0.1.0",
    description="API for managing test effort estimations",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routes
from .routes import router  # noqa: E402

app.include_router(router, prefix="/api")
