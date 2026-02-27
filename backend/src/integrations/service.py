"""Integration service — orchestrates adapters and manages sync operations."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..database.models import IntegrationConfig, Request
from .base import BaseAdapter, ConnectionTestResult, SyncResult, SyncStatus
from .email_adapter import EmailAdapter
from .jira_adapter import JiraAdapter
from .redmine_adapter import RedmineAdapter


ADAPTER_MAP: dict[str, type[BaseAdapter]] = {
    "REDMINE": RedmineAdapter,
    "JIRA": JiraAdapter,
    "EMAIL": EmailAdapter,
}


def get_adapter(system_name: str, session: Session) -> BaseAdapter | None:
    """Create an adapter instance for the given system using stored config."""
    config_row = (
        session.query(IntegrationConfig)
        .filter(IntegrationConfig.system_name == system_name)
        .first()
    )
    if not config_row or not config_row.enabled:
        return None

    adapter_cls = ADAPTER_MAP.get(system_name)
    if not adapter_cls:
        return None

    additional = {}
    if config_row.additional_config_json:
        try:
            additional = json.loads(config_row.additional_config_json)
        except json.JSONDecodeError:
            pass

    config = {
        "base_url": config_row.base_url or "",
        "api_key": config_row.api_key or "",
        "username": config_row.username or "",
        "additional_config": additional,
    }

    return adapter_cls(config)


def test_integration(system_name: str, session: Session) -> ConnectionTestResult:
    """Test connection for a given integration system."""
    adapter = get_adapter(system_name, session)
    if not adapter:
        return ConnectionTestResult(False, f"{system_name} is not configured or not enabled.")
    return adapter.test_connection()


def sync_import(system_name: str, session: Session) -> SyncResult:
    """Import requests from an external system."""
    adapter = get_adapter(system_name, session)
    if not adapter:
        return SyncResult(
            system=system_name,
            direction="IMPORT",
            status=SyncStatus.FAILED,
            errors=[f"{system_name} is not configured or not enabled."],
        )

    result = adapter.import_requests()

    # Update last_sync_at
    config_row = (
        session.query(IntegrationConfig)
        .filter(IntegrationConfig.system_name == system_name)
        .first()
    )
    if config_row:
        config_row.last_sync_at = datetime.now()
        session.commit()

    return result


def sync_export(
    system_name: str,
    estimation_data: dict,
    session: Session,
) -> SyncResult:
    """Export estimation results to an external system."""
    adapter = get_adapter(system_name, session)
    if not adapter:
        return SyncResult(
            system=system_name,
            direction="EXPORT",
            status=SyncStatus.FAILED,
            errors=[f"{system_name} is not configured or not enabled."],
        )
    return adapter.export_estimation(estimation_data)


def get_integration_status(session: Session) -> list[dict]:
    """Get status of all configured integrations."""
    configs = session.query(IntegrationConfig).all()
    statuses = []
    for cfg in configs:
        statuses.append({
            "system_name": cfg.system_name,
            "enabled": cfg.enabled,
            "base_url": cfg.base_url or "",
            "last_sync_at": str(cfg.last_sync_at) if cfg.last_sync_at else None,
            "has_api_key": bool(cfg.api_key),
        })
    return statuses
