"""Background polling scheduler for Redmine auto-sync.

Periodically imports requests from Redmine if configured with a polling interval.
Started on FastAPI app startup if Redmine integration has poll_interval_minutes set.
"""

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _poll_loop(session_factory: sessionmaker, interval_minutes: int) -> None:
    """Background loop that calls sync_import for REDMINE every N minutes."""
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            from .service import sync_import

            db: Session = session_factory()
            try:
                result = sync_import("REDMINE", db)
                logger.info(
                    "Redmine auto-sync completed: %d created, %d updated",
                    result.items_created,
                    result.items_updated,
                )
            finally:
                db.close()
        except Exception:
            logger.exception("Redmine auto-sync failed")


def start_scheduler(session_factory: sessionmaker) -> None:
    """Start the Redmine polling scheduler if configured."""
    global _scheduler_task

    if _scheduler_task is not None:
        return  # Already running

    db: Session = session_factory()
    try:
        from ..database.models import IntegrationConfig

        cfg = (
            db.query(IntegrationConfig)
            .filter(IntegrationConfig.system_name == "REDMINE")
            .first()
        )
        if not cfg or not cfg.enabled:
            return

        additional = json.loads(cfg.additional_config_json or "{}")
        interval = additional.get("poll_interval_minutes")
        if not interval or int(interval) <= 0:
            return

        interval = int(interval)
        logger.info("Starting Redmine auto-sync scheduler (every %d minutes)", interval)

        loop = asyncio.get_event_loop()
        _scheduler_task = loop.create_task(_poll_loop(session_factory, interval))
    except Exception:
        logger.exception("Failed to start Redmine scheduler")
    finally:
        db.close()


def stop_scheduler() -> None:
    """Stop the Redmine polling scheduler."""
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
