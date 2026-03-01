"""Integration service — orchestrates adapters and manages sync operations."""

import json
from datetime import date, datetime

from sqlalchemy.orm import Session, joinedload

try:
    from ..database.models import Configuration, Estimation, EstimationTask, IntegrationConfig, Request
except ImportError:
    from database.models import Configuration, Estimation, EstimationTask, IntegrationConfig, Request  # type: ignore[no-redef]

from .base import BaseAdapter, ConnectionTestResult, ExternalRequest, SyncResult, SyncStatus
from .email_adapter import EmailAdapter
from .jira_adapter import JiraAdapter
from .outline_adapter import OutlineAdapter
from .redmine_adapter import RedmineAdapter


ADAPTER_MAP: dict[str, type[BaseAdapter]] = {
    "REDMINE": RedmineAdapter,
    "JIRA": JiraAdapter,
    "EMAIL": EmailAdapter,
    "OUTLINE": OutlineAdapter,
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


def _generate_request_number(session: Session) -> str:
    """Generate the next REQ-YYYY-NNN number."""
    cfg = session.query(Configuration).filter(Configuration.key == "request_number_prefix").first()
    prefix = cfg.value if cfg else "REQ"
    year = datetime.now().year
    count = session.query(Request).count()
    return f"{prefix}-{year}-{count + 1:03d}"


def _persist_imported_items(
    session: Session, system_name: str, items: list[ExternalRequest]
) -> tuple[int, int]:
    """Persist ExternalRequest items as Request rows.

    Returns (created_count, updated_count).
    """
    created = 0
    updated = 0
    for ext in items:
        # Check for existing request by external_id + source
        existing = (
            session.query(Request)
            .filter(
                Request.external_id == ext.external_id,
                Request.request_source == system_name,
            )
            .first()
        )
        if existing:
            # Update mutable fields
            existing.title = ext.title
            existing.description = ext.description or existing.description
            existing.requester_name = ext.requester_name or existing.requester_name
            existing.priority = ext.priority
            if ext.requested_delivery_date:
                try:
                    existing.requested_delivery_date = date.fromisoformat(
                        ext.requested_delivery_date
                    )
                except (ValueError, TypeError):
                    pass
            updated += 1
        else:
            delivery = None
            if ext.requested_delivery_date:
                try:
                    delivery = date.fromisoformat(ext.requested_delivery_date)
                except (ValueError, TypeError):
                    pass

            req = Request(
                request_number=_generate_request_number(session),
                request_source=system_name,
                external_id=ext.external_id,
                title=ext.title,
                description=ext.description or "",
                requester_name=ext.requester_name or "Unknown",
                priority=ext.priority,
                status="NEW",
                requested_delivery_date=delivery,
                received_date=date.today(),
            )
            session.add(req)
            # Flush so the next _generate_request_number sees this row
            session.flush()
            created += 1

    session.commit()
    return created, updated


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

    # Persist imported items as Request rows
    if result.imported_items:
        created, updated = _persist_imported_items(
            session, system_name, result.imported_items
        )
        result.items_created = created
        result.items_updated = updated

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


def _estimation_to_export_dict(est: "Estimation") -> dict:
    """Convert an Estimation ORM object to the dict expected by adapters."""
    tasks_data = []
    for t in est.tasks:
        tasks_data.append({
            "task_name": t.task_name,
            "task_type": t.task_type,
            "calculated_hours": t.calculated_hours,
        })
    return {
        "estimation_number": est.estimation_number or f"EST-{est.id}",
        "project_name": est.project_name,
        "project_type": est.project_type,
        "status": est.status,
        "feasibility_status": est.feasibility_status,
        "total_tester_hours": est.total_tester_hours,
        "total_leader_hours": est.total_leader_hours,
        "grand_total_hours": est.grand_total_hours,
        "grand_total_days": est.grand_total_days,
        "dut_count": est.dut_count,
        "profile_count": est.profile_count,
        "dut_profile_combinations": est.dut_profile_combinations,
        "pr_fix_count": est.pr_fix_count,
        "created_at": str(est.created_at) if est.created_at else "",
        "assigned_to_name": (est.assigned_to.display_name or est.assigned_to.username) if est.assigned_to else None,
        "tasks": tasks_data,
    }


def sync_export_all(system_name: str, session: Session) -> SyncResult:
    """Export all saved estimations to an external system.

    Iterates over every estimation in the database and calls
    ``adapter.export_estimation()`` for each one.  Returns an aggregate
    SyncResult.
    """
    adapter = get_adapter(system_name, session)
    if not adapter:
        return SyncResult(
            system=system_name,
            direction="EXPORT",
            status=SyncStatus.FAILED,
            errors=[f"{system_name} is not configured or not enabled."],
        )

    estimations = session.query(Estimation).options(
        joinedload(Estimation.assigned_to),
        joinedload(Estimation.tasks),
    ).all()
    if not estimations:
        return SyncResult(
            system=system_name,
            direction="EXPORT",
            status=SyncStatus.SUCCESS,
            items_processed=0,
            errors=["No estimations found to export."],
        )

    total = len(estimations)
    created = 0
    updated = 0
    failed = 0
    errors: list[str] = []

    for est in estimations:
        est_data = _estimation_to_export_dict(est)
        result = adapter.export_estimation(est_data)
        if result.status == SyncStatus.SUCCESS:
            created += result.items_created
            updated += result.items_updated
        else:
            failed += 1
            errors.extend(result.errors)

    # Update last_sync_at
    config_row = (
        session.query(IntegrationConfig)
        .filter(IntegrationConfig.system_name == system_name)
        .first()
    )
    if config_row:
        config_row.last_sync_at = datetime.now()
        session.commit()

    status = SyncStatus.SUCCESS if failed == 0 else (SyncStatus.PARTIAL if created + updated > 0 else SyncStatus.FAILED)

    return SyncResult(
        system=system_name,
        direction="EXPORT",
        status=status,
        items_processed=total,
        items_created=created,
        items_updated=updated,
        items_failed=failed,
        errors=errors,
    )


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
