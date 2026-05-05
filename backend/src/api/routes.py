"""FastAPI REST endpoints for all entities."""

import json
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request as HTTPRequest

from ..database.models import (
    Configuration,
    DocumentType,
    DutType,
    Estimation,
    EstimationRisk,
    EstimationTask,
    EstimationTeamAllocation,
    EstimationVersionSnapshot,
    Feature,
    HistoricalProject,
    PublicHoliday,
    Request,
    RiskItem,
    TaskPreset,
    TaskTemplate,
    TaskTemplateFeature,
    Team,
    TeamMember,
    TestProfile,
    WebhookNotification,
)
from ..engine.calculator import (
    EstimationInput,
    PRFixInput as CalcPRFixInput,
    TaskInput,
    calculate_estimation,
)
from ..engine.calibration import HistoricalDataPoint, calibrate
from ..engine.feasibility import assess_risks
from .app import get_db
from .schemas import (
    CalibrationResultOut,
    CalculateInput,
    CalculationResultOut,
    ConfigurationOut,
    ConfigurationUpdate,
    DashboardStatsOut,
    RecentEstimationOut,
    RecentRequestOut,
    DocumentTypeCreate,
    DocumentTypeOut,
    DocumentTypeUpdate,
    DutTypeCreate,
    DutTypeOut,
    DutTypeUpdate,
    EstimationCreate,
    EstimationOut,
    EstimationTaskOut,
    EstimationRevise,
    EstimationStatusUpdate,
    EstimationUpdate,
    FeatureCreate,
    FeatureOut,
    FeatureUpdate,
    HistoricalProjectCreate,
    HistoricalProjectOut,
    RequestCreate,
    RequestDetailOut,
    RequestOut,
    RequestUpdate,
    RiskItemCreate,
    RiskItemOut,
    RiskItemUpdate,
    TaskPresetCreate,
    TaskPresetOut,
    TaskPresetUpdate,
    TaskTemplateCreate,
    TaskTemplateOut,
    TaskTemplateUpdate,
    TeamAllocationItem,
    TeamCreate,
    TeamMembersUpdate,
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberUpdate,
    TeamOut,
    TeamUpdate,
    TestProfileCreate,
    TestProfileOut,
    TestProfileUpdate,
    UnreadCountOut,
    WebhookNotificationOut,
    PublicHolidayCreate,
    PublicHolidayOut,
    PublicHolidayUpdate,
)
from ..auth.models import AuditLog, User
from ..auth.schemas import (
    AuditLogOut,
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..auth.service import AuthService
from ..auth.dependencies import get_current_user, get_optional_user, RequireRole

router = APIRouter()


# ── Helper ───────────────────────────────────────────────

def _get_config_value(db: Session, key: str, default: str) -> str:
    cfg = db.query(Configuration).filter(Configuration.key == key).first()
    return cfg.value if cfg else default


def _generate_number(db: Session, prefix_key: str, table_class: type, number_field: str) -> str:
    prefix = _get_config_value(db, prefix_key, "EST")
    year = datetime.now().year
    # Count existing records this year to get next sequence
    count = db.query(table_class).count()
    return f"{prefix}-{year}-{count + 1:03d}"


def _get_pr_config(db: Session) -> dict:
    """Read PR configuration values from the database."""
    return {
        "complexity_hours": {
            "simple": float(_get_config_value(db, "pr_hours_simple", "2.0")),
            "medium": float(_get_config_value(db, "pr_hours_medium", "4.0")),
            "complex": float(_get_config_value(db, "pr_hours_complex", "8.0")),
        },
        "no_test_hours": float(_get_config_value(db, "pr_no_test_hours", "8.0")),
        "no_test_task_template_id": _get_config_value(db, "pr_no_test_task_template_id", ""),
    }


def _count_no_test_prs(pr_details: list[dict]) -> int:
    """Count the number of PRs with test_available=false."""
    return sum(1 for pr in pr_details if not pr.get("test_available", True))


def _calc_doc_hours_and_deliverables(
    doc_type_ids: list[int],
    doc_counts: dict[str, int],
    included_template_ids: set[int],
    db: Session,
) -> tuple[float, list[dict]]:
    """Calculate documentation hours and build deliverables with overlap info.

    When multiple document types are linked to the same task template, the
    template's base hours are deducted only ONCE from the combined total of
    those documents (not once per document).

    Returns (documentation_hours, deliverables_list).
    """
    if not doc_type_ids:
        return 0.0, []

    doc_types = db.query(DocumentType).filter(DocumentType.id.in_(doc_type_ids)).all()
    dt_map = {dt.id: dt for dt in doc_types}

    # First pass: build raw deliverable entries and group by linked template
    raw_entries: list[dict] = []
    # template_id → list of indices into raw_entries
    template_groups: dict[int, list[int]] = {}

    for dtid in doc_type_ids:
        dt = dt_map.get(dtid)
        if not dt:
            continue
        count = doc_counts.get(str(dtid), 1)
        total_hours = dt.base_effort_hours * count
        idx = len(raw_entries)
        raw_entries.append({
            "name": dt.name,
            "category": dt.category,
            "count": count,
            "base_effort_hours": dt.base_effort_hours,
            "total_hours": total_hours,
            "effective_hours": total_hours,
            "overlap_note": None,
            "linked_task": dt.task_template.name if dt.task_template else None,
            "_task_template_id": dt.task_template_id,
        })
        if dt.task_template_id and dt.task_template_id in included_template_ids:
            template_groups.setdefault(dt.task_template_id, []).append(idx)

    # Second pass: for each shared template, deduct its hours once from the
    # group total and distribute effective hours proportionally.
    for tmpl_id, indices in template_groups.items():
        linked_tmpl = db.get(TaskTemplate, tmpl_id)
        if not linked_tmpl:
            continue
        deducted = linked_tmpl.base_effort_hours
        group_total = sum(raw_entries[i]["total_hours"] for i in indices)
        group_effective = max(0.0, group_total - deducted)

        for i in indices:
            entry = raw_entries[i]
            proportion = entry["total_hours"] / group_total if group_total > 0 else 0
            entry["effective_hours"] = round(group_effective * proportion, 2)
            entry["overlap_note"] = (
                f"Deducted {deducted:.1f}h across group (already in task '{linked_tmpl.name}')"
            )

    # Build final list (strip internal key) and sum effective hours
    deliverables = []
    documentation_hours = 0.0
    for entry in raw_entries:
        entry.pop("_task_template_id", None)
        deliverables.append(entry)
        documentation_hours += entry["effective_hours"]

    return documentation_hours, deliverables


def _build_doc_synthetic_tasks(deliverables: list[dict]) -> list[dict]:
    """Build synthetic task-breakdown entries for documentation excess hours.

    Groups deliverables by linked task and creates one synthetic task per group
    whose effective_hours > 0.  The task name is
    ``"{linked_task} (additional documentation)"``.
    Deliverables without a linked task that still carry effective hours get a
    generic "Documentation effort" entry.
    """
    # group by linked_task name
    groups: dict[str, float] = {}
    doc_names: dict[str, list[str]] = {}
    for dd in deliverables:
        if dd["effective_hours"] <= 0:
            continue
        key = dd.get("linked_task") or ""
        groups[key] = groups.get(key, 0) + dd["effective_hours"]
        doc_names.setdefault(key, []).append(dd["name"])

    tasks: list[dict] = []
    for key, hours in groups.items():
        if key:
            task_name = f"{key} (additional documentation)"
        else:
            task_name = "Documentation effort"
        detail = ", ".join(doc_names[key])
        tasks.append({
            "task_name": task_name,
            "task_type": "DOCUMENTATION",
            "base_hours": round(hours, 2),
            "calculated_hours": round(hours, 2),
            "leader_hours": 0,
            "is_new_feature_study": False,
            "notes": f"Additional effort for: {detail}",
        })
    return tasks


def _build_pr_no_test_synthetic_tasks(pr_details: list[dict], no_test_hours: float) -> list[dict]:
    """Build synthetic task entries for PRs without existing tests.

    Creates one consolidated task for all no-test PRs with the total hours.
    """
    no_test_prs = [pr for pr in pr_details if not pr.get("test_available", True)]
    if not no_test_prs:
        return []
    count = len(no_test_prs)
    total = count * no_test_hours
    pr_ids = ", ".join(pr.get("pr_number", "?") for pr in no_test_prs)
    return [{
        "task_name": "Test Creation (PR without existing tests)",
        "task_type": "PR_TEST_CREATION",
        "base_hours": no_test_hours,
        "calculated_hours": round(total, 2),
        "leader_hours": 0,
        "is_new_feature_study": False,
        "notes": f"{count} PR(s) without tests: {pr_ids} ({no_test_hours:.1f}h each)",
    }]


def _compute_doc_deliverables(estimation: Estimation, db: Session) -> list[dict]:
    """Compute document deliverables with overlap adjustment info from wizard inputs."""
    wizard = json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {}
    doc_type_ids = wizard.get("document_type_ids", [])
    doc_counts = wizard.get("document_counts", {})
    included_template_ids = {t.task_template_id for t in estimation.tasks if t.task_template_id}
    _, deliverables = _calc_doc_hours_and_deliverables(
        doc_type_ids, doc_counts, included_template_ids, db,
    )
    return deliverables


# ── Authentication ──────────────────────────────────────

@router.post("/auth/login")
def login(data: LoginRequest, request: HTTPRequest, db: Session = Depends(get_db)):
    """Authenticate and get JWT tokens."""
    auth_service = AuthService(db)
    method = getattr(data, "auth_method", "auto") or "auto"

    result = None

    client_ip = getattr(request.state, "client_ip", None)

    # Try local auth (unless method is explicitly "ldap")
    if method in ("auto", "local"):
        result = auth_service.login(data.username, data.password, ip_address=client_ip)

    # Try LDAP if local fails or method is explicitly "ldap"
    if result is None and method in ("auto", "ldap"):
        from ..auth.ldap_provider import LDAPConnectionError, LDAPProvider
        ldap = LDAPProvider(db)
        if ldap.is_configured:
            try:
                ldap_user = ldap.authenticate(data.username, data.password)
            except LDAPConnectionError as exc:
                auth_service.log_action(
                    user_id=None,
                    action="LOGIN_FAILED",
                    resource_type="auth",
                    details={
                        "username": data.username,
                        "auth_method": "ldap",
                        "reason": f"LDAP unreachable: {exc}",
                    },
                    ip_address=client_ip,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"LDAP server unreachable: {exc}",
                )
            if ldap_user:
                access_token = auth_service.create_access_token(ldap_user)
                refresh_token = auth_service.create_refresh_token(ldap_user)
                auth_service.log_action(ldap_user.id, "LOGIN", ip_address=client_ip)
                result = (ldap_user, access_token, refresh_token)
        elif method == "ldap":
            raise HTTPException(
                status_code=400,
                detail="LDAP authentication is not configured",
            )

    if result is None:
        auth_service.log_action(
            user_id=None,
            action="LOGIN_FAILED",
            resource_type="auth",
            details={
                "username": data.username,
                "auth_method": method,
                "reason": "Invalid username or password",
            },
            ip_address=client_ip,
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user, access_token, refresh_token = result
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.get("/auth/providers")
def get_auth_providers(db: Session = Depends(get_db)):
    """Return which authentication providers are available."""
    providers = ["local"]
    ldap_url = _get_config_value(db, "ldap_url", "")
    if ldap_url.strip():
        providers.append("ldap")
    oidc_issuer = _get_config_value(db, "oidc_issuer", "")
    if oidc_issuer.strip():
        providers.append("oidc")
    return {"providers": providers}


@router.post("/auth/refresh")
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    result = auth_service.refresh(data.refresh_token)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user, access_token, new_refresh = result
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=UserOut.model_validate(user),
    )


@router.post("/auth/logout")
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    auth_service.logout(data.refresh_token)
    return {"status": "ok"}


@router.get("/auth/me", response_model=UserOut)
def get_current_user_info(user: User = Depends(get_current_user)):
    return user


@router.post("/auth/change-password")
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    if not auth_service.change_password(user.id, data.current_password, data.new_password):
        raise HTTPException(400, "Current password is incorrect")
    return {"status": "ok"}


# ── Users (ADMIN only) ─────────────────────────────────

@router.get("/users", response_model=list[UserOut])
def list_users(active_only: bool = False, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    return auth_service.list_users(active_only=active_only)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(request: HTTPRequest, data: UserCreate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    existing = auth_service.get_user_by_username(data.username)
    if existing:
        raise HTTPException(400, f"Username '{data.username}' already exists")
    new_user = auth_service.create_user(
        username=data.username,
        display_name=data.display_name,
        password=data.password,
        email=data.email,
        role=data.role,
        auth_provider=data.auth_provider,
        team_member_id=data.team_member_id,
    )
    auth_service.log_action(user.id, "CREATE", "user", new_user.id, ip_address=getattr(request.state, "client_ip", None))
    return new_user


class AssignableUserOut(BaseModel):
    id: int
    display_name: str
    username: str
    role: str
    model_config = {"from_attributes": True}


@router.get("/users/assignable", response_model=list[AssignableUserOut])
def list_assignable_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all active users for assignment dropdowns — any authenticated user."""
    users = db.query(User).filter(User.is_active.is_(True)).all()
    return users


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    return target


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, request: HTTPRequest, data: UserUpdate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    updated = auth_service.update_user(user_id, **data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(404, "User not found")
    auth_service.log_action(user.id, "UPDATE", "user", user_id, ip_address=getattr(request.state, "client_ip", None))
    return updated


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, request: HTTPRequest, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    if user_id == user.id:
        raise HTTPException(400, "Cannot delete your own account")
    auth_service = AuthService(db)
    if not auth_service.delete_user(user_id):
        raise HTTPException(404, "User not found")
    auth_service.log_action(user.id, "DELETE", "user", user_id, ip_address=getattr(request.state, "client_ip", None))


# ── LDAP Sync (ADMIN only) ─────────────────────────────

@router.post("/auth/ldap/sync")
def ldap_sync(request: HTTPRequest, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    from ..auth.ldap_provider import LDAPProvider
    provider = LDAPProvider(db)
    if not provider.is_configured:
        raise HTTPException(400, "LDAP is not configured")
    result = provider.sync_users()
    AuthService(db).log_action(user.id, "LDAP_SYNC", details=result, ip_address=getattr(request.state, "client_ip", None))
    return result


# ── Audit Log (APPROVER+) ──────────────────────────────

@router.get("/audit-log")
def list_audit_log(
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    resource_type: str | None = None,
    user: User = Depends(RequireRole("APPROVER")),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    logs = auth_service.get_audit_log(limit=limit, offset=offset, action=action, resource_type=resource_type)
    result = []
    for log in logs:
        entry = {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details_json": log.details_json,
            "ip_address": log.ip_address,
            "created_at": str(log.created_at) if log.created_at else None,
        }
        result.append(entry)
    return result


# ── Features ─────────────────────────────────────────────

@router.get("/features", response_model=list[FeatureOut])
def list_features(product_type: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Feature)
    if product_type:
        q = q.filter((Feature.product_type == product_type) | (Feature.product_type.is_(None)))
    return q.all()


@router.post("/features", response_model=FeatureOut, status_code=201)
def create_feature(data: FeatureCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    existing = db.query(Feature).filter(
        Feature.name == data.name,
        Feature.category == data.category,
    ).first()
    if existing:
        cat_label = data.category or "(no category)"
        raise HTTPException(
            409,
            f"Feature '{data.name}' already exists in category '{cat_label}'. "
            "Choose a different name or category.",
        )
    feature = Feature(**data.model_dump())
    db.add(feature)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            409,
            f"Feature '{data.name}' already exists in this category.",
        )
    db.refresh(feature)
    return feature


@router.get("/features/{feature_id}", response_model=FeatureOut)
def get_feature(feature_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    return feature


@router.put("/features/{feature_id}", response_model=FeatureOut)
def update_feature(feature_id: int, data: FeatureUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    updates = data.model_dump(exclude_unset=True)
    new_name = updates.get("name", feature.name)
    new_category = updates.get("category", feature.category)
    if (new_name, new_category) != (feature.name, feature.category):
        clash = db.query(Feature).filter(
            Feature.name == new_name,
            Feature.category == new_category,
            Feature.id != feature_id,
        ).first()
        if clash:
            cat_label = new_category or "(no category)"
            raise HTTPException(
                409,
                f"Feature '{new_name}' already exists in category '{cat_label}'. "
                "Choose a different name or category.",
            )
    for key, val in updates.items():
        setattr(feature, key, val)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            409,
            f"Feature '{new_name}' already exists in this category.",
        )
    db.refresh(feature)
    return feature


@router.delete("/features/{feature_id}", status_code=204)
def delete_feature(feature_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    db.delete(feature)
    db.commit()


# ── Task Templates ───────────────────────────────────────

@router.get("/task-templates", response_model=list[TaskTemplateOut])
def list_task_templates(feature_id: int | None = None, product_type: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TaskTemplate)
    if feature_id is not None:
        q = q.filter(TaskTemplate.features.any(Feature.id == feature_id))
    if product_type:
        q = q.filter((TaskTemplate.product_type == product_type) | (TaskTemplate.product_type.is_(None)))
    templates = q.all()
    results = []
    for tmpl in templates:
        out = TaskTemplateOut.model_validate(tmpl)
        out.feature_hours = _resolve_feature_hours(tmpl, db)
        results.append(out)
    return results


def _resolve_feature_hours(tmpl: TaskTemplate, db) -> dict[str, float]:
    """Build feature_hours dict {feature_id_str: base_hours_override} for a template."""
    links = db.query(TaskTemplateFeature).filter(
        TaskTemplateFeature.task_template_id == tmpl.id,
        TaskTemplateFeature.base_hours_override.isnot(None),
    ).all()
    return {str(lnk.feature_id): lnk.base_hours_override for lnk in links}


def _set_feature_links(tmpl: TaskTemplate, fids: list[int], feature_hours: dict[str, float], db) -> None:
    """Set the many-to-many feature links with optional per-feature base_hours."""
    # Remove existing links
    db.query(TaskTemplateFeature).filter(TaskTemplateFeature.task_template_id == tmpl.id).delete()
    db.flush()
    # Create new links
    for fid in fids:
        override = feature_hours.get(str(fid))
        db.add(TaskTemplateFeature(
            task_template_id=tmpl.id,
            feature_id=fid,
            base_hours_override=override,
        ))
    db.flush()
    # Refresh the relationship
    db.expire(tmpl, ["features"])


@router.post("/task-templates", response_model=TaskTemplateOut, status_code=201)
def create_task_template(data: TaskTemplateCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    # Resolve feature_ids (new) or feature_id (legacy)
    fids = data.feature_ids if data.feature_ids else ([data.feature_id] if data.feature_id else [])
    dump = data.model_dump(exclude={"feature_ids", "feature_hours"})
    dump["feature_id"] = fids[0] if len(fids) == 1 else None
    tmpl = TaskTemplate(**dump)
    db.add(tmpl)
    db.flush()
    if fids:
        _set_feature_links(tmpl, fids, data.feature_hours or {}, db)
    db.commit()
    db.refresh(tmpl)
    result = TaskTemplateOut.model_validate(tmpl)
    result.feature_hours = _resolve_feature_hours(tmpl, db)
    return result


@router.put("/task-templates/{template_id}", response_model=TaskTemplateOut)
def update_task_template(template_id: int, data: TaskTemplateUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    tmpl = db.get(TaskTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Task template not found")
    update_data = data.model_dump(exclude_unset=True)
    fids = update_data.pop("feature_ids", None)
    fhours = update_data.pop("feature_hours", None)
    for key, val in update_data.items():
        setattr(tmpl, key, val)
    if fids is not None:
        _set_feature_links(tmpl, fids, fhours or {}, db)
        tmpl.feature_id = fids[0] if len(fids) == 1 else None
    db.commit()
    db.refresh(tmpl)
    result = TaskTemplateOut.model_validate(tmpl)
    result.feature_hours = _resolve_feature_hours(tmpl, db)
    return result


@router.delete("/task-templates/{template_id}", status_code=204)
def delete_task_template(template_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    tmpl = db.get(TaskTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Task template not found")
    db.delete(tmpl)
    db.commit()


# ── DUT Types ────────────────────────────────────────────

@router.get("/dut-types", response_model=list[DutTypeOut])
def list_dut_types(product_type: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(DutType)
    if product_type:
        q = q.filter((DutType.product_type == product_type) | (DutType.product_type.is_(None)))
    return q.all()


@router.post("/dut-types", response_model=DutTypeOut, status_code=201)
def create_dut_type(data: DutTypeCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    dut = DutType(**data.model_dump())
    db.add(dut)
    db.commit()
    db.refresh(dut)
    return dut


@router.put("/dut-types/{dut_id}", response_model=DutTypeOut)
def update_dut_type(dut_id: int, data: DutTypeUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    dut = db.get(DutType, dut_id)
    if not dut:
        raise HTTPException(404, "DUT type not found")
    updates = data.model_dump(exclude_unset=True)
    # Check for name uniqueness only if name is actually changing
    new_name = updates.get("name")
    if new_name and new_name != dut.name:
        existing = db.query(DutType).filter(DutType.name == new_name, DutType.id != dut_id).first()
        if existing:
            raise HTTPException(409, f"DUT type with name '{new_name}' already exists")
    for key, val in updates.items():
        setattr(dut, key, val)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Failed to update — possible duplicate name")
    db.refresh(dut)
    return dut


@router.delete("/dut-types/{dut_id}", status_code=204)
def delete_dut_type(dut_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    dut = db.get(DutType, dut_id)
    if not dut:
        raise HTTPException(404, "DUT type not found")
    db.delete(dut)
    db.commit()


@router.post("/dut-types/reinit")
def reinit_dut_types(user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    """Delete all DUT types and reset the auto-increment ID counter."""
    from sqlalchemy import text
    db.query(DutType).delete()
    db.commit()
    # Reset autoincrement for SQLite and MySQL
    try:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='dut_types'"))
        db.commit()
    except Exception:
        try:
            db.execute(text("ALTER TABLE dut_types AUTO_INCREMENT = 1"))
            db.commit()
        except Exception:
            pass
    return {"status": "ok", "message": "DUT registry cleared, ID counter reset to 1"}


# ── Test Profiles ────────────────────────────────────────

@router.get("/profiles", response_model=list[TestProfileOut])
def list_profiles(product_type: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TestProfile)
    if product_type:
        q = q.filter((TestProfile.product_type == product_type) | (TestProfile.product_type.is_(None)))
    return q.all()


@router.post("/profiles", response_model=TestProfileOut, status_code=201)
def create_profile(data: TestProfileCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    profile = TestProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/profiles/{profile_id}", response_model=TestProfileOut)
def update_profile(profile_id: int, data: TestProfileUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    profile = db.get(TestProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    profile = db.get(TestProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()


# ── Historical Projects ──────────────────────────────────

@router.get("/historical-projects", response_model=list[HistoricalProjectOut])
def list_historical_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(HistoricalProject).all()


@router.post("/historical-projects", response_model=HistoricalProjectOut, status_code=201)
def create_historical_project(data: HistoricalProjectCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    proj = HistoricalProject(**data.model_dump())
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


@router.put("/historical-projects/{project_id}", response_model=HistoricalProjectOut)
def update_historical_project(project_id: int, data: HistoricalProjectCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    proj = db.get(HistoricalProject, project_id)
    if not proj:
        raise HTTPException(404, "Historical project not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(proj, key, val)
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/historical-projects/{project_id}", status_code=204)
def delete_historical_project(project_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    proj = db.get(HistoricalProject, project_id)
    if not proj:
        raise HTTPException(404, "Historical project not found")
    db.delete(proj)
    db.commit()


@router.post("/estimations/{estimation_id}/archive", response_model=HistoricalProjectOut, status_code=201)
def archive_estimation_to_history(estimation_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    """Convert an APPROVED estimation into a historical project record."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    if estimation.status != "APPROVED":
        raise HTTPException(400, f"Only APPROVED estimations can be archived (current: {estimation.status})")

    # Check for existing archive
    existing = db.query(HistoricalProject).filter(HistoricalProject.estimation_id == estimation_id).first()
    if existing:
        raise HTTPException(400, "This estimation has already been archived")

    wizard = json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {}

    proj = HistoricalProject(
        project_name=estimation.project_name,
        project_type=estimation.project_type,
        estimated_hours=estimation.grand_total_hours,
        dut_count=estimation.dut_count,
        profile_count=estimation.profile_count,
        pr_count=estimation.pr_fix_count,
        features_json=json.dumps(wizard.get("feature_ids", [])),
        notes=f"Archived from estimation {estimation.estimation_number or estimation_id}",
        estimation_id=estimation.id,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


# ── Team Members ─────────────────────────────────────────

@router.get("/team-members", response_model=list[TeamMemberOut])
def list_team_members(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.query(TeamMember).all()
    result = []
    for m in members:
        out = TeamMemberOut.model_validate(m)
        linked_user = db.query(User).filter(User.team_member_id == m.id).first()
        if linked_user:
            out.linked_user_id = linked_user.id
            out.linked_user_name = linked_user.display_name or linked_user.username
        result.append(out)
    return result


@router.post("/team-members", response_model=TeamMemberOut, status_code=201)
def create_team_member(data: TeamMemberCreate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    member = TeamMember(**data.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/team-members/{member_id}", response_model=TeamMemberOut)
def update_team_member(member_id: int, data: TeamMemberUpdate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(member, key, val)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/team-members/{member_id}", status_code=204)
def delete_team_member(member_id: int, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found")
    db.delete(member)
    db.commit()


# ── Requests ─────────────────────────────────────────────

@router.get("/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Request)
    if status:
        q = q.filter(Request.status == status)
    return q.order_by(Request.created_at.desc()).all()


@router.post("/requests", response_model=RequestOut, status_code=201)
def create_request(data: RequestCreate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    req_data = data.model_dump()
    req = Request(**req_data)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    return req


@router.put("/requests/{request_id}", response_model=RequestOut)
def update_request(request_id: int, data: RequestUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(req, key, val)
    db.commit()
    db.refresh(req)
    return req


# ── Configuration ────────────────────────────────────────

@router.get("/configuration/branding")
def get_branding(db: Session = Depends(get_db)):
    """Return branding config (logo) without authentication."""
    logo_url = _get_config_value(db, "logo_url", "")
    logo_height = _get_config_value(db, "logo_height", "50")
    return {"logo_url": logo_url, "logo_height": logo_height}


@router.get("/configuration", response_model=list[ConfigurationOut])
def list_configuration(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Configuration).all()


@router.get("/dut-categories", response_model=list[str])
def get_dut_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the configured DUT categories as a list of strings."""
    raw = _get_config_value(db, "dut_categories", "SIM,eSIM,UICC,IoT Device,Mobile Device,Other")
    return [c.strip() for c in raw.split(",") if c.strip()]


@router.get("/feature-categories", response_model=list[str])
def get_feature_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the configured feature categories as a list of strings."""
    raw = _get_config_value(db, "feature_categories", "Telecom,Security,Platform,Other")
    return [c.strip() for c in raw.split(",") if c.strip()]


@router.get("/project-types", response_model=list[str])
def get_project_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the configured project types as a list of strings."""
    raw = _get_config_value(db, "project_types", "NEW,EVOLUTION,SUPPORT,CHANGE_REQUEST")
    return [c.strip() for c in raw.split(",") if c.strip()]


@router.get("/configuration/product_types", response_model=list[str])
def get_product_types(db: Session = Depends(get_db)):
    """Return the configured product types as a list of strings."""
    raw = _get_config_value(db, "product_types", '["Payment", "Telco"]')
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/configuration/team_skills", response_model=list[str])
def get_team_skills(db: Session = Depends(get_db)):
    """Return the configured team skills as a list of strings."""
    default = '["Test Execution","Test Design","Automation","Performance","Security","API Testing","Mobile Testing","Regression"]'
    raw = _get_config_value(db, "team_skills", default)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


@router.put("/configuration/{key}", response_model=ConfigurationOut)
def update_configuration(key: str, data: ConfigurationUpdate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    cfg = db.get(Configuration, key)
    if not cfg:
        # Upsert: create the key if it doesn't exist yet
        cfg = Configuration(key=key, value=data.value, description="")
        db.add(cfg)
    else:
        cfg.value = data.value
    db.commit()
    db.refresh(cfg)
    return cfg


# ── Estimations ──────────────────────────────────────────


def _expand_templates_to_tasks(
    templates: list,
    features: list,
    selected_feature_ids: list[int],
    new_feature_ids: list[int],
    db=None,
    skip_pr_fix: bool = False,
) -> list[TaskInput]:
    """Expand task templates into TaskInput list.

    Global templates (no linked features) produce one task.
    Feature-linked templates produce one task per selected feature they're linked to.
    Per-feature base_hours_override from task_template_features is used when available.
    When skip_pr_fix is True, templates flagged as is_pr_fix are excluded.
    """
    task_inputs: list[TaskInput] = []
    selected_set = set(selected_feature_ids)
    feature_map = {f.id: f for f in features}

    # Pre-load all per-feature hour overrides for these templates
    override_map: dict[tuple[int, int], float] = {}
    if db is not None:
        tmpl_ids = [t.id for t in templates]
        if tmpl_ids:
            links = db.query(TaskTemplateFeature).filter(
                TaskTemplateFeature.task_template_id.in_(tmpl_ids),
                TaskTemplateFeature.base_hours_override.isnot(None),
            ).all()
            for lnk in links:
                override_map[(lnk.task_template_id, lnk.feature_id)] = lnk.base_hours_override

    for tmpl in templates:
        if skip_pr_fix and getattr(tmpl, "is_pr_fix", False):
            continue
        linked_fids = [f.id for f in tmpl.features]
        if not linked_fids:
            # Global template — one task, no feature association
            task_inputs.append(TaskInput(
                name=tmpl.name,
                task_type=tmpl.task_type,
                base_effort_hours=tmpl.base_effort_hours,
                scales_with_dut=tmpl.scales_with_dut,
                scales_with_profile=tmpl.scales_with_profile,
                complexity_weight=1.0,
                is_new_feature_study=False,
                is_parallelizable=tmpl.is_parallelizable,
                template_id=tmpl.id,
            ))
        else:
            # One task per selected feature this template is linked to
            for fid in linked_fids:
                if fid in selected_set:
                    feat = feature_map.get(fid)
                    if not feat:
                        continue
                    is_study = fid in new_feature_ids
                    # Use per-feature base_hours override if set, else template default
                    base_hrs = override_map.get((tmpl.id, fid), tmpl.base_effort_hours)
                    task_inputs.append(TaskInput(
                        name=tmpl.name,
                        task_type=tmpl.task_type,
                        base_effort_hours=base_hrs,
                        scales_with_dut=tmpl.scales_with_dut,
                        scales_with_profile=tmpl.scales_with_profile,
                        complexity_weight=feat.complexity_weight,
                        is_new_feature_study=is_study,
                        is_parallelizable=tmpl.is_parallelizable,
                        template_id=tmpl.id,
                        feature_id=fid,
                        feature_name=feat.name,
                    ))
    return task_inputs


@router.post("/estimations/calculate", response_model=CalculationResultOut)
def calculate_estimation_preview(data: CalculateInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run calculation from wizard inputs without persisting to DB."""
    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))
    pr_scales_profile = _get_config_value(db, "pr_scales_with_profile", "false").lower() == "true"

    feature_ids = data.resolved_feature_ids
    new_feature_ids = data.resolved_new_feature_ids
    delivery = data.expected_delivery or data.delivery_date

    if feature_ids:
        features = db.query(Feature).filter(Feature.id.in_(feature_ids)).all()
        templates = db.query(TaskTemplate).filter(
            TaskTemplate.features.any(Feature.id.in_(feature_ids)) | ~TaskTemplate.features.any()
        ).all()
    else:
        features = []
        templates = db.query(TaskTemplate).filter(~TaskTemplate.features.any()).all()

    pr_total = data.pr_fixes.simple + data.pr_fixes.medium + data.pr_fixes.complex_
    task_inputs = _expand_templates_to_tasks(
        templates, features, feature_ids, new_feature_ids, db,
        skip_pr_fix=(pr_total == 0),
    )

    dut_count = len(data.dut_ids) if data.dut_ids else 1
    profile_count = len(data.profile_ids) if data.profile_ids else 1
    combination_count = len(data.dut_profile_matrix) if data.dut_profile_matrix else dut_count * profile_count
    new_feature_count = len(new_feature_ids)

    # Build per-feature study hours list
    feature_study_hours_list: list[float] = []
    for fid in new_feature_ids:
        feat = next((f for f in features if f.id == fid), None)
        hrs = feat.study_effort_hours if feat and feat.study_effort_hours is not None else study_hours_cfg
        feature_study_hours_list.append(hrs)

    release_factor = float(_get_config_value(db, "release_effort_factor", "0.5"))
    release_task_types_raw = _get_config_value(db, "release_effort_task_types", "EXECUTION")
    release_task_types = [t.strip() for t in release_task_types_raw.split(",") if t.strip()]
    pr_cfg = _get_pr_config(db)

    calc_input = EstimationInput(
        project_type=data.project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        combination_count=combination_count,
        pr_fixes=CalcPRFixInput(
            simple=data.pr_fixes.simple,
            medium=data.pr_fixes.medium,
            complex=data.pr_fixes.complex_,
        ),
        new_feature_count=new_feature_count,
        feature_study_hours_list=feature_study_hours_list,
        team_size=data.team_size,
        has_leader=data.has_leader,
        working_days=data.working_days,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
        pr_scales_with_profile=pr_scales_profile,
        expected_releases=data.expected_releases,
        release_effort_factor=release_factor,
        release_effort_task_types=release_task_types,
        pr_complexity_hours=pr_cfg["complexity_hours"],
        pr_no_test_hours=pr_cfg["no_test_hours"],
        pr_no_test_count=0,  # preview doesn't have pr_details
    )
    result = calculate_estimation(calc_input)

    ref_ids = data.reference_project_ids or []
    risks = assess_risks(
        total_features=len(feature_ids),
        new_feature_count=new_feature_count,
        reference_project_count=len(ref_ids),
        delivery_date=delivery,
        dut_profile_combinations=len(data.dut_profile_matrix) if data.dut_profile_matrix else dut_count * profile_count,
    )

    # Calculate documentation hours — deduct linked template hours once per
    # template group to avoid double-counting.
    included_template_ids = {tmpl.id for tmpl in templates}
    documentation_hours, _ = _calc_doc_hours_and_deliverables(
        data.document_type_ids, data.document_counts, included_template_ids, db,
    )

    # Add documentation hours to grand total
    adjusted_grand_total = result.grand_total_hours + documentation_hours
    adjusted_grand_total_days = adjusted_grand_total / hours_per_day if hours_per_day else result.grand_total_days

    # Append user-selected risk registry items to risk messages
    all_risk_messages = list(risks.messages)
    if data.risk_item_ids:
        registry_risks = db.query(RiskItem).filter(RiskItem.id.in_(data.risk_item_ids)).all()
        for ri in registry_risks:
            label = f"[{ri.category}] " if ri.category else ""
            level = ""
            if ri.likelihood or ri.impact:
                level = f" (Likelihood: {ri.likelihood or '?'}, Impact: {ri.impact or '?'})"
            all_risk_messages.append(f"{label}{ri.name}{level}")

    return CalculationResultOut(
        tasks=[
            {
                "name": t.name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "calculated_hours": t.calculated_hours,
                "formula": t.formula,
                "feature_name": t.feature_name,
            }
            for t in result.tasks
        ],
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        pr_fix_hours=result.pr_fix_hours,
        pr_no_test_hours=result.pr_no_test_total_hours,
        study_hours=result.study_hours,
        release_extra_hours=result.release_extra_hours,
        documentation_hours=documentation_hours,
        buffer_hours=result.buffer_hours,
        grand_total_hours=adjusted_grand_total,
        grand_total_days=adjusted_grand_total_days,
        feasibility_status=result.feasibility_status,
        capacity_hours=result.capacity_hours,
        utilization_pct=result.utilization_pct,
        elapsed_hours=result.elapsed_hours,
        elapsed_days=result.elapsed_days,
        elapsed_weeks=result.elapsed_weeks,
        risk_flags=[f.value for f in risks.flags],
        risk_messages=all_risk_messages,
    )


@router.get("/estimations", response_model=list[EstimationOut])
def list_estimations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Estimation).order_by(Estimation.created_at.desc()).all()


@router.get("/estimations/{estimation_id}", response_model=EstimationOut)
def get_estimation(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    est = db.get(Estimation, estimation_id)
    if not est:
        raise HTTPException(404, "Estimation not found")
    # Compute document deliverables with overlap info from wizard inputs
    doc_deliverables = _compute_doc_deliverables(est, db)
    result = EstimationOut.model_validate(est)
    result.document_deliverables = doc_deliverables
    # Append synthetic tasks for documentation excess hours
    for st in _build_doc_synthetic_tasks(doc_deliverables):
        result.tasks.append(EstimationTaskOut(
            id=0,
            task_template_id=None,
            task_name=st["task_name"],
            task_type=st["task_type"],
            base_hours=st["base_hours"],
            calculated_hours=st["calculated_hours"],
            assigned_testers=0,
            has_leader_support=False,
            leader_hours=0,
            is_new_feature_study=False,
            notes=st["notes"],
        ))
    # Append synthetic tasks for PRs without existing tests
    wizard = json.loads(est.wizard_inputs_json) if est.wizard_inputs_json else {}
    pr_details = wizard.get("pr_details", [])
    pr_no_test_hrs_cfg = float(_get_config_value(db, "pr_no_test_hours", "8.0"))
    for st in _build_pr_no_test_synthetic_tasks(pr_details, pr_no_test_hrs_cfg):
        result.tasks.append(EstimationTaskOut(
            id=0,
            task_template_id=None,
            task_name=st["task_name"],
            task_type=st["task_type"],
            base_hours=st["base_hours"],
            calculated_hours=st["calculated_hours"],
            assigned_testers=0,
            has_leader_support=False,
            leader_hours=0,
            is_new_feature_study=False,
            notes=st["notes"],
        ))
    return result


@router.post("/estimations", response_model=EstimationOut, status_code=201)
def create_estimation(data: EstimationCreate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Create a new estimation: resolve inputs, run calculation, save result."""
    # Resolve config
    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))
    pr_scales_profile = _get_config_value(db, "pr_scales_with_profile", "false").lower() == "true"

    # Resolve features and their task templates (many-to-many)
    if data.feature_ids:
        features = db.query(Feature).filter(Feature.id.in_(data.feature_ids)).all()
        templates = db.query(TaskTemplate).filter(
            TaskTemplate.features.any(Feature.id.in_(data.feature_ids)) | ~TaskTemplate.features.any()
        ).all()
    else:
        features = []
        templates = db.query(TaskTemplate).filter(~TaskTemplate.features.any()).all()

    dut_count = len(data.dut_ids) if data.dut_ids else 1
    profile_count = len(data.profile_ids) if data.profile_ids else 1
    combinations = len(data.dut_profile_matrix) if data.dut_profile_matrix else dut_count * profile_count
    new_feature_count = len(data.new_feature_ids)
    pr_total = data.pr_fixes.simple + data.pr_fixes.medium + data.pr_fixes.complex_

    # Build task inputs — one per feature for feature-linked templates
    task_inputs = _expand_templates_to_tasks(
        templates, features, data.feature_ids, data.new_feature_ids, db,
        skip_pr_fix=(pr_total == 0),
    )

    release_factor = float(_get_config_value(db, "release_effort_factor", "0.5"))
    release_task_types_raw = _get_config_value(db, "release_effort_task_types", "EXECUTION")
    release_task_types = [t.strip() for t in release_task_types_raw.split(",") if t.strip()]
    pr_cfg = _get_pr_config(db)
    pr_details_raw = [d.model_dump() for d in data.pr_details] if data.pr_details else []
    no_test_count = _count_no_test_prs(pr_details_raw)

    # Build per-feature study hours list
    feature_study_hours_list: list[float] = []
    for fid in data.new_feature_ids:
        feat = next((f for f in features if f.id == fid), None)
        hrs = feat.study_effort_hours if feat and feat.study_effort_hours is not None else study_hours_cfg
        feature_study_hours_list.append(hrs)

    # Run calculation
    calc_input = EstimationInput(
        project_type=data.project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        combination_count=combinations,
        pr_fixes=CalcPRFixInput(
            simple=data.pr_fixes.simple,
            medium=data.pr_fixes.medium,
            complex=data.pr_fixes.complex_,
        ),
        new_feature_count=new_feature_count,
        feature_study_hours_list=feature_study_hours_list,
        team_size=data.team_size,
        has_leader=data.has_leader,
        working_days=data.working_days,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
        pr_scales_with_profile=pr_scales_profile,
        expected_releases=data.expected_releases,
        release_effort_factor=release_factor,
        release_effort_task_types=release_task_types,
        pr_complexity_hours=pr_cfg["complexity_hours"],
        pr_no_test_hours=pr_cfg["no_test_hours"],
        pr_no_test_count=no_test_count,
    )
    result = calculate_estimation(calc_input)

    # Generate estimation number
    est_number = _generate_number(db, "estimation_number_prefix", Estimation, "estimation_number")

    # Serialize wizard inputs for later revision
    wizard_inputs = {
        "feature_ids": data.feature_ids,
        "new_feature_ids": data.new_feature_ids,
        "reference_project_ids": data.reference_project_ids,
        "dut_ids": data.dut_ids,
        "profile_ids": data.profile_ids,
        "dut_profile_matrix": data.dut_profile_matrix,
        "pr_fixes": {
            "simple": data.pr_fixes.simple,
            "medium": data.pr_fixes.medium,
            "complex": data.pr_fixes.complex_,
        },
        "pr_details": pr_details_raw,
        "team_size": data.team_size,
        "has_leader": data.has_leader,
        "working_days": data.working_days,
        "start_date": str(data.start_date) if data.start_date else None,
        "expected_releases": data.expected_releases,
        "document_type_ids": data.document_type_ids,
        "document_counts": data.document_counts,
        "project_reference": data.project_reference,
        "testing_start_date": data.testing_start_date,
        "product_type_filter": data.product_type_filter,
    }

    # Calculate documentation hours — deduct linked template hours once per group
    included_template_ids = {tmpl.id for tmpl in templates}
    documentation_hours, _ = _calc_doc_hours_and_deliverables(
        data.document_type_ids, data.document_counts, included_template_ids, db,
    )

    adjusted_grand_total = result.grand_total_hours + documentation_hours
    adjusted_grand_total_days = adjusted_grand_total / hours_per_day if hours_per_day else result.grand_total_days

    # Compute estimated completion date from testing start + elapsed days
    estimated_completion = None
    if data.testing_start_date and result.elapsed_days > 0:
        try:
            _testing_start = date.fromisoformat(data.testing_start_date)
            estimated_completion = _compute_completion_date(_testing_start, result.elapsed_days, db)
        except (ValueError, TypeError):
            pass

    # Save estimation
    estimation = Estimation(
        request_id=data.request_id,
        estimation_number=est_number,
        project_name=data.project_name,
        project_type=data.project_type,
        reference_project_ids=json.dumps(data.reference_project_ids),
        dut_count=dut_count,
        profile_count=profile_count,
        dut_profile_combinations=combinations,
        pr_fix_count=pr_total,
        start_date=data.start_date,
        expected_delivery=data.expected_delivery,
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        pr_fix_hours=result.pr_fix_hours,
        pr_no_test_hours=result.pr_no_test_total_hours,
        study_hours=result.study_hours,
        release_extra_hours=result.release_extra_hours,
        documentation_hours=documentation_hours,
        buffer_hours=result.buffer_hours,
        grand_total_hours=adjusted_grand_total,
        grand_total_days=adjusted_grand_total_days,
        elapsed_hours=result.elapsed_hours,
        elapsed_days=result.elapsed_days,
        elapsed_weeks=result.elapsed_weeks,
        feasibility_status=result.feasibility_status,
        status="DRAFT",
        created_by=data.created_by,
        version=1,
        wizard_inputs_json=json.dumps(wizard_inputs),
        expected_releases=data.expected_releases,
        project_goals=data.project_goals,
        target_customer=data.target_customer,
        project_reference=data.project_reference,
        team_id=data.team_id,
        estimated_completion_date=estimated_completion,
    )
    db.add(estimation)
    db.flush()

    # Save tasks
    for task in result.tasks:
        et = EstimationTask(
            estimation_id=estimation.id,
            task_template_id=task.template_id,
            task_name=task.name,
            task_type=task.task_type,
            base_hours=task.base_hours,
            calculated_hours=task.calculated_hours,
            assigned_testers=data.task_assigned_testers.get(task.name, 1),
            has_leader_support=data.has_leader,
            leader_hours=task.calculated_hours * leader_ratio if data.has_leader else 0,
            is_new_feature_study=task.is_new_feature_study,
            formula=task.formula,
            feature_id=task.feature_id,
            feature_name=task.feature_name,
        )
        db.add(et)

    # Save team allocations
    for alloc in data.team_allocations:
        eta = EstimationTeamAllocation(
            estimation_id=estimation.id,
            team_member_id=alloc.team_member_id,
            role=alloc.role,
            allocated_hours=alloc.allocated_hours,
        )
        db.add(eta)

    # Save risk associations
    for rid in data.risk_item_ids:
        db.add(EstimationRisk(estimation_id=estimation.id, risk_item_id=rid))

    # Update request status if linked
    if data.request_id:
        req = db.get(Request, data.request_id)
        if req:
            req.status = "ESTIMATED"

    db.commit()
    db.refresh(estimation)
    return estimation


@router.post("/estimations/{estimation_id}/calculate", response_model=CalculationResultOut)
def recalculate_estimation(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Recalculate an existing estimation and return the results."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))

    # Build task inputs from existing estimation tasks
    task_inputs = [
        TaskInput(
            name=t.task_name,
            task_type=t.task_type,
            base_effort_hours=t.base_hours,
            scales_with_dut=False,  # Already calculated
            scales_with_profile=False,
            complexity_weight=1.0,
            is_new_feature_study=t.is_new_feature_study,
            template_id=t.task_template_id,
            feature_id=t.feature_id,
            feature_name=t.feature_name,
        )
        for t in estimation.tasks
    ]

    new_feature_count = sum(1 for t in estimation.tasks if t.is_new_feature_study)

    calc_input = EstimationInput(
        project_type=estimation.project_type,
        tasks=task_inputs,
        dut_count=1,  # Already baked into base_hours
        profile_count=1,
        new_feature_count=new_feature_count,
        team_size=max(1, sum(t.assigned_testers for t in estimation.tasks) // max(len(estimation.tasks), 1)),
        has_leader=any(t.has_leader_support for t in estimation.tasks),
        working_days=20,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
    )

    result = calculate_estimation(calc_input)

    # Risk assessment
    ref_ids = json.loads(estimation.reference_project_ids) if estimation.reference_project_ids else []
    risks = assess_risks(
        total_features=0,
        new_feature_count=new_feature_count,
        reference_project_count=len(ref_ids),
        delivery_date=estimation.expected_delivery,
        dut_profile_combinations=estimation.dut_profile_combinations,
    )

    # Append user-selected risk registry items
    all_risk_messages = list(risks.messages)
    for er in estimation.risks:
        ri = er.risk_item
        if ri:
            label = f"[{ri.category}] " if ri.category else ""
            level = ""
            if ri.likelihood or ri.impact:
                level = f" (Likelihood: {ri.likelihood or '?'}, Impact: {ri.impact or '?'})"
            all_risk_messages.append(f"{label}{ri.name}{level}")

    return CalculationResultOut(
        tasks=[
            {
                "name": t.name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "calculated_hours": t.calculated_hours,
                "formula": t.formula,
                "feature_name": t.feature_name,
            }
            for t in result.tasks
        ],
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        pr_fix_hours=result.pr_fix_hours,
        study_hours=result.study_hours,
        release_extra_hours=result.release_extra_hours,
        buffer_hours=result.buffer_hours,
        grand_total_hours=result.grand_total_hours,
        grand_total_days=result.grand_total_days,
        feasibility_status=result.feasibility_status,
        capacity_hours=result.capacity_hours,
        utilization_pct=result.utilization_pct,
        elapsed_hours=result.elapsed_hours,
        elapsed_days=result.elapsed_days,
        elapsed_weeks=result.elapsed_weeks,
        risk_flags=[f.value for f in risks.flags],
        risk_messages=all_risk_messages,
    )


# ── Completion date helper ────────────────────────────────

def _compute_completion_date(start: date, elapsed_days: float, db: Session) -> date:
    """Walk forward from start by elapsed_days working days, skipping weekends and holidays."""
    from datetime import timedelta
    all_holidays = db.query(PublicHoliday).all()
    holidays: set[date] = set()
    for h in all_holidays:
        if h.is_recurring:
            for y in range(start.year, start.year + 3):
                try:
                    holidays.add(date(y, h.date.month, h.date.day))
                except ValueError:
                    pass
        else:
            holidays.add(h.date)
    remaining = elapsed_days
    current = start
    while remaining > 0:
        if current.weekday() < 5 and current not in holidays:
            remaining -= 1
        current += timedelta(days=1)
    return current - timedelta(days=1)


# ── Report generation endpoints ──────────────────────────

def _build_report_data(estimation: Estimation, db: Session) -> "ExcelReportData":
    """Build the shared report data object from an estimation."""
    from ..reports.excel_report import ExcelReportData

    # Get request info if linked
    req = estimation.request
    ref_ids = json.loads(estimation.reference_project_ids) if estimation.reference_project_ids else []
    ref_projects = []
    if ref_ids:
        refs = db.query(HistoricalProject).filter(HistoricalProject.id.in_(ref_ids)).all()
        ref_projects = [
            {
                "project_name": r.project_name,
                "project_type": r.project_type,
                "estimated_hours": r.estimated_hours,
                "actual_hours": r.actual_hours,
                "dut_count": r.dut_count,
                "profile_count": r.profile_count,
                "pr_count": r.pr_count,
            }
            for r in refs
        ]

    tasks = []
    for t in estimation.tasks:
        td: dict = {
            "task_name": t.task_name,
            "task_type": t.task_type,
            "base_hours": t.base_hours,
            "calculated_hours": t.calculated_hours,
            "leader_hours": t.leader_hours,
            "is_new_feature_study": t.is_new_feature_study,
            "notes": t.notes or "",
            "feature_name": t.feature_name,
        }
        tasks.append(td)

    # Resolve DUT/profile names and matrix from wizard_inputs_json
    wizard = json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {}
    dut_ids = wizard.get("dut_ids", [])
    profile_ids = wizard.get("profile_ids", [])
    dut_profile_matrix = wizard.get("dut_profile_matrix", [])
    pr_fixes_data = wizard.get("pr_fixes", {})

    dut_types_data = []
    if dut_ids:
        duts = db.query(DutType).filter(DutType.id.in_(dut_ids)).all()
        dut_types_data = [{"id": d.id, "name": d.name} for d in duts]

    profiles_data = []
    if profile_ids:
        profiles = db.query(TestProfile).filter(TestProfile.id.in_(profile_ids)).all()
        profiles_data = [{"id": p.id, "name": p.name} for p in profiles]

    # PR details from wizard inputs
    pr_details = wizard.get("pr_details", [])

    # Build team members data from allocations
    team_members_data = []
    for alloc in estimation.team_allocations:
        tm = alloc.team_member
        team_members_data.append({
            "name": tm.name if tm else "Unknown",
            "role": alloc.role or (tm.role if tm else ""),
            "hours_per_day": tm.available_hours_per_day if tm else 7.0,
            "skills": tm.skills_json if tm else "[]",
            "allocated_hours": alloc.allocated_hours,
        })

    # Calculate capacity and utilization
    team_size = wizard.get("team_size", 1)
    has_leader = wizard.get("has_leader", False)
    working_days = wizard.get("working_days", 20)
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    capacity_hours = team_size * working_days * hours_per_day
    if has_leader:
        capacity_hours += working_days * hours_per_day
    utilization_pct = (estimation.grand_total_hours / capacity_hours * 100) if capacity_hours > 0 else 0

    # Build document deliverables data with overlap adjustment info
    doc_type_ids = wizard.get("document_type_ids", [])
    doc_counts = wizard.get("document_counts", {})
    included_template_ids = {t.task_template_id for t in estimation.tasks if t.task_template_id}
    _, doc_deliverables = _calc_doc_hours_and_deliverables(
        doc_type_ids, doc_counts, included_template_ids, db,
    )

    # Append synthetic tasks for documentation excess hours so they appear
    # in the task breakdown alongside template-based tasks.
    tasks.extend(_build_doc_synthetic_tasks(doc_deliverables))

    # Append synthetic tasks for PRs without existing tests
    pr_details = wizard.get("pr_details", [])
    pr_no_test_hrs_cfg = float(_get_config_value(db, "pr_no_test_hours", "8.0"))
    tasks.extend(_build_pr_no_test_synthetic_tasks(pr_details, pr_no_test_hrs_cfg))

    # Compute working weeks
    grand_total_days = estimation.grand_total_days or 0
    working_weeks = round(grand_total_days / 5.0, 1)

    return ExcelReportData(
        project_name=estimation.project_name,
        estimation_number=estimation.estimation_number or "",
        project_type=estimation.project_type,
        created_by=estimation.created_by,
        created_at=str(estimation.created_at.date()) if estimation.created_at else "",
        request_number=req.request_number if req else None,
        requester_name=req.requester_name if req else None,
        business_unit=req.business_unit if req else None,
        priority=req.priority if req else None,
        dut_count=estimation.dut_count,
        profile_count=estimation.profile_count,
        dut_profile_combinations=estimation.dut_profile_combinations,
        pr_fix_count=estimation.pr_fix_count,
        expected_delivery=str(estimation.expected_delivery) if estimation.expected_delivery else "",
        total_tester_hours=estimation.total_tester_hours,
        total_leader_hours=estimation.total_leader_hours,
        pr_fix_hours=estimation.pr_fix_hours,
        study_hours=estimation.study_hours,
        buffer_hours=estimation.buffer_hours,
        grand_total_hours=estimation.grand_total_hours,
        grand_total_days=estimation.grand_total_days,
        feasibility_status=estimation.feasibility_status,
        capacity_hours=capacity_hours,
        utilization_pct=utilization_pct,
        tasks=tasks,
        dut_types=dut_types_data,
        profiles=profiles_data,
        dut_profile_matrix=dut_profile_matrix,
        pr_simple=pr_fixes_data.get("simple", 0),
        pr_medium=pr_fixes_data.get("medium", 0),
        pr_complex=pr_fixes_data.get("complex", 0),
        reference_projects=ref_projects,
        pr_details=pr_details,
        team_members=team_members_data,
        team_size=team_size,
        has_leader=has_leader,
        risk_messages=_build_risk_messages(estimation, db),
        release_extra_hours=estimation.release_extra_hours,
        documentation_hours=getattr(estimation, "documentation_hours", 0) or 0,
        pr_no_test_hours=getattr(estimation, "pr_no_test_hours", 0) or 0,
        project_goals=estimation.project_goals,
        target_customer=estimation.target_customer,
        version=estimation.version or 1,
        status=estimation.status,
        start_date=str(estimation.start_date) if estimation.start_date else "",
        testing_start_date=wizard.get("testing_start_date", ""),
        document_deliverables=doc_deliverables,
        working_weeks=working_weeks,
        working_hours_per_day=hours_per_day,
    )


def _build_risk_messages(estimation: Estimation, db: Session) -> list[str]:
    """Build combined risk messages from auto-assessment + registry items."""
    wizard = json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {}
    new_feature_ids = wizard.get("new_feature_ids", [])
    feature_ids = wizard.get("feature_ids", [])
    ref_ids = json.loads(estimation.reference_project_ids) if estimation.reference_project_ids else []

    risks = assess_risks(
        total_features=len(feature_ids),
        new_feature_count=len(new_feature_ids),
        reference_project_count=len(ref_ids),
        delivery_date=estimation.expected_delivery,
        dut_profile_combinations=estimation.dut_profile_combinations,
    )
    messages = list(risks.messages)

    # Append user-selected risk registry items
    for er in estimation.risks:
        ri = er.risk_item
        if ri:
            label = f"[{ri.category}] " if ri.category else ""
            level = ""
            if ri.likelihood or ri.impact:
                level = f" (Likelihood: {ri.likelihood or '?'}, Impact: {ri.impact or '?'})"
            messages.append(f"{label}{ri.name}{level}")

    return messages


@router.get("/estimations/{estimation_id}/report/xlsx")
def download_excel_report(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..reports.excel_report import generate_excel_report
    report_data = _build_report_data(estimation, db)
    content = generate_excel_report(report_data)

    filename = f"{estimation.estimation_number or f'EST-{estimation_id}'}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/estimations/{estimation_id}/report/docx")
def download_word_report(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..reports.word_report import generate_word_report
    report_data = _build_report_data(estimation, db)
    content = generate_word_report(report_data)

    filename = f"{estimation.estimation_number or f'EST-{estimation_id}'}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/estimations/{estimation_id}/report/pdf")
def download_pdf_report(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..reports.pdf_report import generate_pdf_report
    report_data = _build_report_data(estimation, db)
    content = generate_pdf_report(report_data)

    filename = f"{estimation.estimation_number or f'EST-{estimation_id}'}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Integrations ─────────────────────────────────────────

from ..database.models import IntegrationConfig


class IntegrationConfigOut(BaseModel):
    id: int
    system_name: str
    base_url: Optional[str] = None
    username: Optional[str] = None
    additional_config_json: str = "{}"
    enabled: bool = False
    last_sync_at: Optional[datetime] = None
    has_api_key: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, row: IntegrationConfig) -> "IntegrationConfigOut":
        return cls(
            id=row.id,
            system_name=row.system_name,
            base_url=row.base_url,
            username=row.username,
            additional_config_json=row.additional_config_json or "{}",
            enabled=row.enabled,
            last_sync_at=row.last_sync_at,
            has_api_key=bool(row.api_key),
        )


class IntegrationConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    additional_config_json: Optional[str] = None
    enabled: Optional[bool] = None


class SyncResultOut(BaseModel):
    system: str
    direction: str
    status: str
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_failed: int = 0
    errors: list[str] = []


class ConnectionTestOut(BaseModel):
    success: bool
    message: str
    details: dict = {}


@router.get("/integrations")
def list_integrations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    configs = db.query(IntegrationConfig).all()
    return [IntegrationConfigOut.from_model(c).model_dump() for c in configs]


@router.get("/integrations/{system_name}")
def get_integration(system_name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == system_name.upper()).first()
    if not cfg:
        raise HTTPException(404, f"Integration {system_name} not found")
    return IntegrationConfigOut.from_model(cfg).model_dump()


@router.put("/integrations/{system_name}")
def update_integration(system_name: str, data: IntegrationConfigUpdate, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)) -> dict:
    system_name = system_name.upper()
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == system_name).first()
    if not cfg:
        # Create new
        cfg = IntegrationConfig(system_name=system_name)
        db.add(cfg)

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(cfg, key, val)
    db.commit()
    db.refresh(cfg)
    return IntegrationConfigOut.from_model(cfg).model_dump()


@router.post("/integrations/{system_name}/test")
def test_integration_endpoint(system_name: str, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)) -> dict:
    from ..integrations.service import test_integration
    result = test_integration(system_name.upper(), db)
    return ConnectionTestOut(
        success=result.success,
        message=result.message,
        details=result.details,
    ).model_dump()


@router.post("/integrations/{system_name}/sync")
def trigger_sync(system_name: str, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)) -> dict:
    name = system_name.upper()

    # Outline is export-only: push estimations to wiki.
    # All other integrations import requests.
    if name == "OUTLINE":
        from ..integrations.service import sync_export_all
        result = sync_export_all(name, db)
    else:
        from ..integrations.service import sync_import
        result = sync_import(name, db)

    return SyncResultOut(
        system=result.system,
        direction=result.direction,
        status=result.status.value,
        items_processed=result.items_processed,
        items_created=result.items_created,
        items_updated=result.items_updated,
        items_failed=result.items_failed,
        errors=result.errors,
    ).model_dump()


@router.get("/integrations/{system_name}/status")
def integration_health(system_name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == system_name.upper()).first()
    if not cfg:
        raise HTTPException(404, f"Integration {system_name} not found")
    return {
        "system_name": cfg.system_name,
        "enabled": cfg.enabled,
        "last_sync_at": str(cfg.last_sync_at) if cfg.last_sync_at else None,
        "configured": bool(cfg.base_url or cfg.api_key),
    }


# ── Redmine Webhook ──────────────────────────────────────

@router.post("/webhooks/redmine")
def redmine_webhook(request: HTTPRequest, db: Session = Depends(get_db)):
    """Handle incoming Redmine webhook payloads (no auth — uses shared secret)."""
    import hmac
    import hashlib

    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == "REDMINE").first()
    if not cfg or not cfg.enabled:
        raise HTTPException(400, "Redmine integration is not enabled")

    additional = json.loads(cfg.additional_config_json or "{}")
    webhook_secret = additional.get("webhook_secret", "")

    # Validate secret via query param if configured
    if webhook_secret:
        import urllib.parse
        qs = urllib.parse.parse_qs(str(request.query_params))
        token = qs.get("token", [""])[0] if isinstance(qs.get("token"), list) else qs.get("token", "")
        if not hmac.compare_digest(str(token), webhook_secret):
            raise HTTPException(403, "Invalid webhook token")

    # Process payload asynchronously
    try:
        from ..integrations.service import sync_import
        result = sync_import("REDMINE", db)

        # Create notifications for configured watchers
        if result.items_created > 0:
            try:
                watchers_raw = _get_config_value(db, "webhook_watchers", "[]")
                watcher_ids = json.loads(watchers_raw)
                if isinstance(watcher_ids, list):
                    for uid in watcher_ids:
                        db.add(WebhookNotification(
                            user_id=int(uid),
                            title=f"{result.items_created} new request(s) imported",
                            message=f"Redmine webhook imported {result.items_created} new request(s).",
                            source="REDMINE",
                        ))
                    db.commit()
            except Exception:
                pass  # Don't break webhook response for notification failures

        return {"status": "ok", "items_created": result.items_created, "items_updated": result.items_updated}
    except Exception as e:
        raise HTTPException(500, f"Webhook processing failed: {str(e)}")


# ── Webhook Notifications ────────────────────────────────

@router.get("/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """List notifications for the current user (unread first, newest first, limit 50)."""
    notifs = (
        db.query(WebhookNotification)
        .filter(WebhookNotification.user_id == user.id)
        .order_by(WebhookNotification.is_read.asc(), WebhookNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [WebhookNotificationOut.model_validate(n).model_dump() for n in notifs]


@router.get("/notifications/unread-count")
def unread_notification_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Return the count of unread notifications for badge polling."""
    count = (
        db.query(WebhookNotification)
        .filter(WebhookNotification.user_id == user.id, WebhookNotification.is_read == False)  # noqa: E712
        .count()
    )
    return UnreadCountOut(unread_count=count).model_dump()


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Mark a single notification as read (ownership check)."""
    notif = db.get(WebhookNotification, notification_id)
    if not notif or notif.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    notif.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/mark-all-read")
def mark_all_notifications_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Mark all notifications as read for the current user."""
    db.query(WebhookNotification).filter(
        WebhookNotification.user_id == user.id,
        WebhookNotification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ── Send report via email ────────────────────────────────

@router.post("/estimations/{estimation_id}/send-report")
def send_estimation_report(estimation_id: int, to_email: str, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)) -> dict:
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..integrations.service import get_adapter
    adapter = get_adapter("EMAIL", db)
    if not adapter:
        raise HTTPException(400, "Email integration is not configured or not enabled.")

    from ..reports.pdf_report import generate_pdf_report
    report_data = _build_report_data(estimation, db)
    pdf_bytes = generate_pdf_report(report_data)

    from ..integrations.email_adapter import EmailAdapter
    if not isinstance(adapter, EmailAdapter):
        raise HTTPException(500, "Invalid email adapter")

    result = adapter.send_estimation_report(
        to_email=to_email,
        estimation_number=estimation.estimation_number or "",
        project_name=estimation.project_name,
        grand_total_hours=estimation.grand_total_hours,
        feasibility_status=estimation.feasibility_status,
        report_bytes=pdf_bytes,
        report_filename=f"{estimation.estimation_number or 'report'}.pdf",
    )

    if result.status.value == "SUCCESS":
        return {"status": "ok", "message": f"Report sent to {to_email}"}
    raise HTTPException(500, f"Failed to send: {'; '.join(result.errors)}")


# ── Estimation CRUD (update, delete, status) ─────────────

@router.put("/estimations/{estimation_id}", response_model=EstimationOut)
def update_estimation(estimation_id: int, data: EstimationUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Update estimation metadata (project name, type, delivery date, notes)."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(estimation, key, val)
    db.commit()
    db.refresh(estimation)
    return estimation


@router.delete("/estimations/{estimation_id}", status_code=204)
def delete_estimation(estimation_id: int, user: User = Depends(RequireRole("ADMIN")), db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    db.delete(estimation)
    db.commit()


@router.post("/estimations/{estimation_id}/status", response_model=EstimationOut)
def update_estimation_status(estimation_id: int, data: EstimationStatusUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Update estimation status following the workflow: DRAFT -> FINAL -> APPROVED."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    valid_transitions = {
        "DRAFT": ["FINAL", "REVISED"],
        "FINAL": ["APPROVED", "REVISED"],
        "APPROVED": ["REVISED"],
        "REVISED": ["DRAFT"],
    }

    current = estimation.status
    target = data.status
    allowed = valid_transitions.get(current, [])
    if target not in allowed:
        raise HTTPException(
            400,
            f"Invalid status transition: {current} -> {target}. Allowed: {allowed}",
        )

    estimation.status = target
    if target == "APPROVED":
        estimation.approved_by = data.approved_by
        estimation.approved_at = datetime.now()
    elif target == "REVISED":
        # Reset approval on revision
        estimation.approved_by = None
        estimation.approved_at = None

    db.commit()
    db.refresh(estimation)

    # Send notification
    try:
        from ..notifications.service import NotificationService
        notifier = NotificationService(db)
        notifier.notify_estimation_status_changed(
            estimation.estimation_number or f"EST-{estimation.id}",
            estimation.project_name,
            current,
            target,
            user.display_name,
            estimation.grand_total_hours,
            creator_user_id=estimation.created_by_id,
            assigned_user_id=estimation.assigned_to_id,
        )
    except Exception:
        pass

    # Auto-export to external system when estimation is finalized or approved
    if target in ("FINAL", "APPROVED") and estimation.request_id:
        _try_export_estimation(estimation, db)

    # Auto-export to Outline wiki if configured for this status
    _try_outline_auto_export(estimation, target, db)

    # Auto-create historical project if configured (Task 5)
    try:
        auto_rule = _get_config_value(db, "auto_create_historical_project", "manual")
        trigger_status = {"on_approve": "APPROVED", "on_complete": "FINAL"}.get(auto_rule)
        if trigger_status and target == trigger_status:
            existing_hp = db.query(HistoricalProject).filter(
                HistoricalProject.estimation_id == estimation.id,
            ).first()
            if not existing_hp:
                hp = HistoricalProject(
                    project_name=estimation.project_name,
                    project_type=estimation.project_type,
                    estimated_hours=estimation.grand_total_hours,
                    dut_count=estimation.dut_count,
                    profile_count=estimation.profile_count,
                    pr_count=estimation.pr_fix_count,
                    estimation_id=estimation.id,
                )
                db.add(hp)
                db.commit()
    except Exception:
        pass

    return estimation


def _try_export_estimation(estimation: "Estimation", db: Session) -> None:
    """Attempt to export estimation results back to the originating external system."""
    req = db.get(Request, estimation.request_id)
    if not req or not req.external_id or req.request_source == "MANUAL":
        return

    try:
        from ..integrations.service import sync_export

        estimation_data = {
            "external_id": req.external_id,
            "grand_total_hours": estimation.grand_total_hours,
            "feasibility_status": estimation.feasibility_status,
            "estimation_number": estimation.estimation_number or f"EST-{estimation.id}",
            "project_name": estimation.project_name,
            "status": estimation.status,
        }
        sync_export(req.request_source, estimation_data, db)
        logger.info(
            "Auto-exported estimation %s to %s (external_id=%s)",
            estimation.estimation_number or estimation.id,
            req.request_source,
            req.external_id,
        )
    except Exception:
        logger.warning(
            "Auto-export failed for estimation %s to %s (external_id=%s)",
            estimation.estimation_number or estimation.id,
            req.request_source,
            req.external_id,
            exc_info=True,
        )


def _try_outline_auto_export(estimation: "Estimation", new_status: str, db: Session) -> None:
    """Export to Outline wiki if the new status matches the configured auto-export states."""
    try:
        auto_states_raw = _get_config_value(db, "outline_auto_export_states", "")
        if not auto_states_raw.strip():
            return
        auto_states = [s.strip().upper() for s in auto_states_raw.split(",") if s.strip()]
        if new_status.upper() not in auto_states:
            return

        from ..integrations.service import get_adapter, _estimation_to_export_dict
        adapter = get_adapter("OUTLINE", db)
        if not adapter:
            return

        est_data = _estimation_to_export_dict(estimation)
        adapter.export_estimation(est_data)
    except Exception:
        # Auto-export failure must NOT block the status transition
        pass


@router.put("/estimations/{estimation_id}/revise", response_model=EstimationOut)
def revise_estimation(estimation_id: int, request: HTTPRequest, data: EstimationRevise, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Revise an estimation: re-run calculation with new inputs, bump version, reset to DRAFT."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    if estimation.status != "REVISED":
        raise HTTPException(400, f"Estimation must be in REVISED status to revise (current: {estimation.status})")

    # Resolve config
    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))
    pr_scales_profile = _get_config_value(db, "pr_scales_with_profile", "false").lower() == "true"

    # Resolve features and their task templates (many-to-many)
    if data.feature_ids:
        features = db.query(Feature).filter(Feature.id.in_(data.feature_ids)).all()
        templates = db.query(TaskTemplate).filter(
            TaskTemplate.features.any(Feature.id.in_(data.feature_ids)) | ~TaskTemplate.features.any()
        ).all()
    else:
        features = []
        templates = db.query(TaskTemplate).filter(~TaskTemplate.features.any()).all()

    dut_count = len(data.dut_ids) if data.dut_ids else 1
    profile_count = len(data.profile_ids) if data.profile_ids else 1
    combinations = len(data.dut_profile_matrix) if data.dut_profile_matrix else dut_count * profile_count
    new_feature_count = len(data.new_feature_ids)
    pr_total = data.pr_fixes.simple + data.pr_fixes.medium + data.pr_fixes.complex_

    # Build task inputs — one per feature for feature-linked templates
    task_inputs = _expand_templates_to_tasks(
        templates, features, data.feature_ids, data.new_feature_ids, db,
        skip_pr_fix=(pr_total == 0),
    )

    release_factor = float(_get_config_value(db, "release_effort_factor", "0.5"))
    release_task_types_raw = _get_config_value(db, "release_effort_task_types", "EXECUTION")
    release_task_types = [t.strip() for t in release_task_types_raw.split(",") if t.strip()]
    pr_cfg = _get_pr_config(db)
    pr_details_raw = [d.model_dump() for d in data.pr_details] if data.pr_details else []
    no_test_count = _count_no_test_prs(pr_details_raw)

    # Build per-feature study hours list
    feature_study_hours_list: list[float] = []
    for fid in data.new_feature_ids:
        feat = next((f for f in features if f.id == fid), None)
        hrs = feat.study_effort_hours if feat and feat.study_effort_hours is not None else study_hours_cfg
        feature_study_hours_list.append(hrs)

    # Run calculation
    calc_input = EstimationInput(
        project_type=data.project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        combination_count=combinations,
        pr_fixes=CalcPRFixInput(
            simple=data.pr_fixes.simple,
            medium=data.pr_fixes.medium,
            complex=data.pr_fixes.complex_,
        ),
        new_feature_count=new_feature_count,
        feature_study_hours_list=feature_study_hours_list,
        team_size=data.team_size,
        has_leader=data.has_leader,
        working_days=data.working_days,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
        pr_scales_with_profile=pr_scales_profile,
        expected_releases=data.expected_releases,
        release_effort_factor=release_factor,
        release_effort_task_types=release_task_types,
        pr_complexity_hours=pr_cfg["complexity_hours"],
        pr_no_test_hours=pr_cfg["no_test_hours"],
        pr_no_test_count=no_test_count,
    )
    result = calculate_estimation(calc_input)

    # Serialize wizard inputs
    wizard_inputs = {
        "feature_ids": data.feature_ids,
        "new_feature_ids": data.new_feature_ids,
        "reference_project_ids": data.reference_project_ids,
        "dut_ids": data.dut_ids,
        "profile_ids": data.profile_ids,
        "dut_profile_matrix": data.dut_profile_matrix,
        "pr_fixes": {
            "simple": data.pr_fixes.simple,
            "medium": data.pr_fixes.medium,
            "complex": data.pr_fixes.complex_,
        },
        "pr_details": pr_details_raw,
        "team_size": data.team_size,
        "has_leader": data.has_leader,
        "working_days": data.working_days,
        "start_date": str(data.start_date) if data.start_date else None,
        "expected_releases": data.expected_releases,
        "document_type_ids": data.document_type_ids,
        "document_counts": data.document_counts,
        "project_reference": data.project_reference,
        "testing_start_date": data.testing_start_date,
        "product_type_filter": data.product_type_filter,
    }

    # Calculate documentation hours — deduct linked template hours once per group
    included_template_ids = {tmpl.id for tmpl in templates}
    documentation_hours, _ = _calc_doc_hours_and_deliverables(
        data.document_type_ids, data.document_counts, included_template_ids, db,
    )

    adjusted_grand_total = result.grand_total_hours + documentation_hours
    adjusted_grand_total_days = adjusted_grand_total / hours_per_day if hours_per_day else result.grand_total_days

    # Save a snapshot of the current version before overwriting
    snapshot_data = {
        "project_name": estimation.project_name,
        "project_type": estimation.project_type,
        "dut_count": estimation.dut_count,
        "profile_count": estimation.profile_count,
        "dut_profile_combinations": estimation.dut_profile_combinations,
        "pr_fix_count": estimation.pr_fix_count,
        "start_date": str(estimation.start_date) if estimation.start_date else None,
        "expected_delivery": str(estimation.expected_delivery) if estimation.expected_delivery else None,
        "total_tester_hours": estimation.total_tester_hours,
        "total_leader_hours": estimation.total_leader_hours,
        "pr_fix_hours": estimation.pr_fix_hours,
        "study_hours": estimation.study_hours,
        "buffer_hours": estimation.buffer_hours,
        "grand_total_hours": estimation.grand_total_hours,
        "grand_total_days": estimation.grand_total_days,
        "feasibility_status": estimation.feasibility_status,
        "status": estimation.status,
        "expected_releases": estimation.expected_releases,
        "release_extra_hours": estimation.release_extra_hours,
        "project_goals": estimation.project_goals,
        "target_customer": estimation.target_customer,
        "wizard_inputs": json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {},
        "tasks": [
            {"task_name": t.task_name, "task_type": t.task_type, "base_hours": t.base_hours, "calculated_hours": t.calculated_hours}
            for t in estimation.tasks
        ],
        "team_allocations": [
            {"member_name": a.team_member.name if a.team_member else "Unknown", "role": a.role, "allocated_hours": a.allocated_hours}
            for a in estimation.team_allocations
        ],
        "risks": [
            {"risk_name": r.risk_item.name if r.risk_item else "Unknown", "notes": r.notes}
            for r in estimation.risks
        ],
    }
    snapshot = EstimationVersionSnapshot(
        estimation_id=estimation.id,
        version=estimation.version or 1,
        snapshot_json=json.dumps(snapshot_data),
    )
    db.add(snapshot)

    # Update estimation in-place
    estimation.project_name = data.project_name
    estimation.project_type = data.project_type
    estimation.reference_project_ids = json.dumps(data.reference_project_ids)
    estimation.dut_count = dut_count
    estimation.profile_count = profile_count
    estimation.dut_profile_combinations = combinations
    estimation.pr_fix_count = pr_total
    estimation.start_date = data.start_date
    estimation.expected_delivery = data.expected_delivery
    estimation.total_tester_hours = result.total_tester_hours
    estimation.total_leader_hours = result.total_leader_hours
    estimation.pr_fix_hours = result.pr_fix_hours
    estimation.pr_no_test_hours = result.pr_no_test_total_hours
    estimation.study_hours = result.study_hours
    estimation.release_extra_hours = result.release_extra_hours
    estimation.documentation_hours = documentation_hours
    estimation.buffer_hours = result.buffer_hours
    estimation.grand_total_hours = adjusted_grand_total
    estimation.grand_total_days = adjusted_grand_total_days
    estimation.elapsed_hours = result.elapsed_hours
    estimation.elapsed_days = result.elapsed_days
    estimation.elapsed_weeks = result.elapsed_weeks
    # Compute estimated completion date from testing start + elapsed days
    if data.testing_start_date and result.elapsed_days > 0:
        try:
            _testing_start_rev = date.fromisoformat(data.testing_start_date)
            estimation.estimated_completion_date = _compute_completion_date(_testing_start_rev, result.elapsed_days, db)
        except (ValueError, TypeError):
            estimation.estimated_completion_date = None
    else:
        estimation.estimated_completion_date = None
    estimation.feasibility_status = result.feasibility_status
    estimation.expected_releases = data.expected_releases
    estimation.project_goals = data.project_goals
    estimation.target_customer = data.target_customer
    estimation.project_reference = data.project_reference
    estimation.team_id = data.team_id
    estimation.status = "DRAFT"
    estimation.version = (estimation.version or 1) + 1
    estimation.wizard_inputs_json = json.dumps(wizard_inputs)
    estimation.approved_by = None
    estimation.approved_at = None

    # Delete old tasks, create new ones
    db.query(EstimationTask).filter(EstimationTask.estimation_id == estimation_id).delete()
    for task in result.tasks:
        et = EstimationTask(
            estimation_id=estimation.id,
            task_template_id=task.template_id,
            task_name=task.name,
            task_type=task.task_type,
            base_hours=task.base_hours,
            calculated_hours=task.calculated_hours,
            assigned_testers=data.task_assigned_testers.get(task.name, 1),
            has_leader_support=data.has_leader,
            leader_hours=task.calculated_hours * leader_ratio if data.has_leader else 0,
            is_new_feature_study=task.is_new_feature_study,
            formula=task.formula,
            feature_id=task.feature_id,
            feature_name=task.feature_name,
        )
        db.add(et)

    # Delete old team allocations, create new ones
    db.query(EstimationTeamAllocation).filter(EstimationTeamAllocation.estimation_id == estimation_id).delete()
    for alloc in data.team_allocations:
        eta = EstimationTeamAllocation(
            estimation_id=estimation.id,
            team_member_id=alloc.team_member_id,
            role=alloc.role,
            allocated_hours=alloc.allocated_hours,
        )
        db.add(eta)

    # Delete old risks, create new ones
    db.query(EstimationRisk).filter(EstimationRisk.estimation_id == estimation_id).delete()
    for rid in data.risk_item_ids:
        db.add(EstimationRisk(estimation_id=estimation.id, risk_item_id=rid))

    # Audit log
    try:
        audit = AuditLog(
            user_id=user.id,
            action="REVISE_ESTIMATION",
            resource_type="estimation",
            resource_id=estimation.id,
            details_json=json.dumps({"new_version": estimation.version}),
            ip_address=getattr(request.state, "client_ip", None),
        )
        db.add(audit)
    except Exception:
        pass

    db.commit()
    db.refresh(estimation)
    return estimation


@router.post("/estimations/{estimation_id}/export")
def export_estimation_to_external(estimation_id: int, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Manually export estimation results to the linked external system (Redmine/Jira)."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    if not estimation.request_id:
        raise HTTPException(400, "Estimation is not linked to a request")

    req = db.get(Request, estimation.request_id)
    if not req or not req.external_id:
        raise HTTPException(400, "Linked request has no external ID")
    if req.request_source == "MANUAL":
        raise HTTPException(400, "Request source is MANUAL — no external system to export to")

    from ..integrations.service import sync_export

    estimation_data = {
        "external_id": req.external_id,
        "grand_total_hours": estimation.grand_total_hours,
        "feasibility_status": estimation.feasibility_status,
        "estimation_number": estimation.estimation_number or f"EST-{estimation.id}",
        "project_name": estimation.project_name,
        "status": estimation.status,
    }
    result = sync_export(req.request_source, estimation_data, db)

    return {
        "status": result.status.value,
        "system": result.system,
        "items_updated": result.items_updated,
        "errors": result.errors,
    }


class ExportTasksInput(BaseModel):
    target_system: str | None = None
    issue_key: str | None = None


@router.post("/estimations/{estimation_id}/export-tasks")
def export_task_breakdown(
    estimation_id: int,
    body: ExportTasksInput | None = None,
    user: User = Depends(RequireRole("ESTIMATOR")),
    db: Session = Depends(get_db),
):
    """Export estimation task breakdown as sub-tasks to Jira or Redmine.

    If no target_system is given, auto-detects from the linked request.
    If issue_key is provided, tasks are created as sub-tasks under it.
    Otherwise, tasks are created as standalone issues in the configured project.
    """
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    target_system = body.target_system if body else None
    issue_key = body.issue_key if body else None

    # Determine target system and external_id
    system_name = None
    external_id = issue_key  # explicit issue key takes priority

    if target_system:
        system_name = target_system.upper()
    elif estimation.request_id:
        req = db.get(Request, estimation.request_id)
        if req and req.request_source != "MANUAL":
            system_name = req.request_source
            if not external_id and req.external_id:
                external_id = req.external_id

    if not system_name:
        # Try to find any enabled integration that supports task breakdown
        from ..integrations.service import get_adapter
        for sys in ["JIRA", "REDMINE"]:
            adapter = get_adapter(sys, db)
            if adapter and hasattr(adapter, "create_task_breakdown"):
                system_name = sys
                break

    if not system_name:
        raise HTTPException(400, "No target system specified and no enabled integration found (Jira/Redmine)")

    from ..integrations.service import _estimation_to_export_dict, sync_export_task_breakdown

    estimation_data = _estimation_to_export_dict(estimation)
    if external_id:
        estimation_data["external_id"] = external_id

    result = sync_export_task_breakdown(system_name, estimation_data, db)

    return {
        "status": result.status.value,
        "system": result.system,
        "items_created": result.items_created,
        "items_processed": result.items_processed,
        "errors": result.errors,
    }


# ── Request detail with linked estimations ───────────────

@router.get("/requests/{request_id}/detail", response_model=RequestDetailOut)
def get_request_detail(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get request with all linked estimations."""
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    return req


# ── Request attachment upload ────────────────────────────

@router.post("/requests/{request_id}/attachments")
async def upload_attachment(request_id: int, file: UploadFile = File(...), user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    """Upload an attachment to a request."""
    import os

    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")

    # Create attachment directory
    attach_dir = os.path.join("data", "attachments", req.request_number)
    os.makedirs(attach_dir, exist_ok=True)

    # Save file
    filepath = os.path.join(attach_dir, file.filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Update attachments_json
    attachments = json.loads(req.attachments_json or "[]")
    attachments.append({
        "filename": file.filename,
        "filepath": filepath,
        "file_size_bytes": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "uploaded_at": datetime.now().isoformat(),
        "source": "MANUAL",
        "external_url": None,
    })
    req.attachments_json = json.dumps(attachments)
    db.commit()

    return {"status": "ok", "filename": file.filename, "size": len(content)}


# ── Logo upload ─────────────────────────────────────────

@router.post("/configuration/logo/upload")
async def upload_logo(
    file: UploadFile = File(...),
    user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    """Upload a logo image and update the logo_url configuration."""
    import os
    import time

    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    ext = os.path.splitext(file.filename or "logo.png")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Invalid file type '{ext}'. Allowed: {', '.join(allowed_ext)}")

    # Use same upload dir as the static mount in app.py
    upload_dir = "/app/data/uploads" if os.path.isdir("/app/data") else os.path.join("data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Clean up any prior `logo.*` files (potentially with a different
    # extension) so the directory only ever has the current logo.
    try:
        for _existing in os.listdir(upload_dir):
            if _existing.startswith("logo.") and _existing != f"logo{ext}":
                try:
                    os.remove(os.path.join(upload_dir, _existing))
                except OSError:
                    pass
    except OSError:
        pass

    filename = f"logo{ext}"
    filepath = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Append a cache-busting version stamp so the browser fetches the new
    # bytes after upload, even when the filename is unchanged.
    cache_bust = int(time.time())
    logo_url = f"/api/static/uploads/{filename}?v={cache_bust}"

    cfg = db.get(Configuration, "logo_url")
    if cfg:
        cfg.value = logo_url
    else:
        db.add(Configuration(key="logo_url", value=logo_url, description="Logo image URL"))
    db.commit()

    return {"status": "ok", "logo_url": logo_url, "size": len(content)}


# ── Calibration endpoint ────────────────────────────────

@router.post("/estimations/{estimation_id}/calibrate", response_model=CalibrationResultOut)
def calibrate_estimation(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Apply historical calibration to an estimation."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    ref_ids = json.loads(estimation.reference_project_ids) if estimation.reference_project_ids else []
    if not ref_ids:
        raise HTTPException(400, "No reference projects linked to this estimation.")

    refs = db.query(HistoricalProject).filter(HistoricalProject.id.in_(ref_ids)).all()
    if not refs:
        raise HTTPException(400, "No reference projects found.")

    from ..engine.calibration import HistoricalDataPoint, calibrate

    data_points = [
        HistoricalDataPoint(
            project_name=r.project_name,
            estimated_hours=r.estimated_hours or 0,
            actual_hours=r.actual_hours or 0,
            feature_ids=json.loads(r.features_json) if r.features_json else [],
        )
        for r in refs
        if r.estimated_hours and r.actual_hours
    ]

    if not data_points:
        raise HTTPException(400, "Reference projects lack estimated/actual hours data.")

    cal_result = calibrate(data_points, current_feature_ids=[])

    adjusted_total = estimation.grand_total_hours * cal_result.suggested_adjustment

    ref_details = [
        {
            "project_name": r.project_name,
            "estimated_hours": r.estimated_hours,
            "actual_hours": r.actual_hours,
            "accuracy_ratio": round(r.actual_hours / r.estimated_hours, 2) if r.estimated_hours else None,
        }
        for r in refs
    ]

    return CalibrationResultOut(
        accuracy_ratio=round(cal_result.accuracy_ratio, 3),
        adjustment_factor=round(cal_result.suggested_adjustment, 3),
        suggestion=cal_result.message,
        reference_projects=ref_details,
        adjusted_grand_total=round(adjusted_total, 1),
    )


# ── Dashboard stats ─────────────────────────────────────

@router.get("/dashboard/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get aggregate statistics for the dashboard."""
    from sqlalchemy import func as sqlfunc

    total_requests = db.query(Request).count()
    requests_new = db.query(Request).filter(Request.status == "NEW").count()
    requests_in_progress = db.query(Request).filter(Request.status.in_(["IN_ESTIMATION", "IN_PROGRESS"])).count()
    requests_completed = db.query(Request).filter(Request.status == "COMPLETED").count()

    total_estimations = db.query(Estimation).count()
    estimations_draft = db.query(Estimation).filter(Estimation.status == "DRAFT").count()
    estimations_final = db.query(Estimation).filter(Estimation.status == "FINAL").count()
    estimations_approved = db.query(Estimation).filter(Estimation.status == "APPROVED").count()

    avg_hours = db.query(sqlfunc.avg(Estimation.grand_total_hours)).scalar() or 0

    # Recent estimations (last 50)
    recent_est = db.query(Estimation).order_by(
        Estimation.created_at.desc()
    ).limit(50).all()
    recent_estimations = [
        RecentEstimationOut(
            id=e.id,
            estimation_number=e.estimation_number,
            project_name=e.project_name,
            grand_total_hours=round(e.grand_total_hours, 1),
            feasibility_status=e.feasibility_status,
            status=e.status,
            version=getattr(e, "version", 1) or 1,
            created_at=e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else None,
        )
        for e in recent_est
    ]

    # Recent requests (last 50)
    recent_req = db.query(Request).order_by(
        Request.created_at.desc()
    ).limit(50).all()
    recent_requests = [
        RecentRequestOut(
            id=r.id,
            request_number=r.request_number,
            title=r.title,
            priority=r.priority,
            status=r.status,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None,
        )
        for r in recent_req
    ]

    # Feature catalog breakdown by category
    feat_rows = db.query(
        sqlfunc.coalesce(Feature.category, "Uncategorized"), sqlfunc.count()
    ).group_by(sqlfunc.coalesce(Feature.category, "Uncategorized")).all()
    features_by_category = {cat: cnt for cat, cnt in feat_rows}

    # Task template breakdown by task_type
    task_rows = db.query(
        TaskTemplate.task_type, sqlfunc.count()
    ).group_by(TaskTemplate.task_type).all()
    tasks_by_type = {tt: cnt for tt, cnt in task_rows}

    # Risk registry breakdown by category and likelihood
    risk_cat_rows = db.query(
        sqlfunc.coalesce(RiskItem.category, "General"), sqlfunc.count()
    ).group_by(sqlfunc.coalesce(RiskItem.category, "General")).all()
    risks_by_category = {cat: cnt for cat, cnt in risk_cat_rows}

    risk_lh_rows = db.query(
        RiskItem.likelihood, sqlfunc.count()
    ).group_by(RiskItem.likelihood).all()
    risks_by_likelihood = {lh: cnt for lh, cnt in risk_lh_rows}

    return DashboardStatsOut(
        total_requests=total_requests,
        requests_new=requests_new,
        requests_in_progress=requests_in_progress,
        requests_completed=requests_completed,
        total_estimations=total_estimations,
        estimations_draft=estimations_draft,
        estimations_final=estimations_final,
        estimations_approved=estimations_approved,
        avg_grand_total_hours=round(float(avg_hours), 1),
        recent_estimations=recent_estimations,
        recent_requests=recent_requests,
        features_by_category=features_by_category,
        tasks_by_type=tasks_by_type,
        risks_by_category=risks_by_category,
        risks_by_likelihood=risks_by_likelihood,
    )


# ── Bulk Import ─────────────────────────────────────────

@router.post("/import/{entity_type}/preview")
async def preview_import_endpoint(
    entity_type: str,
    file: UploadFile = File(...),
    user: User = Depends(RequireRole("ESTIMATOR")),
):
    from ..imports.service import preview_import
    content = await file.read()
    return preview_import(content, entity_type, file.filename or "data.csv")


@router.post("/import/{entity_type}")
async def execute_import_endpoint(
    entity_type: str,
    request: HTTPRequest,
    file: UploadFile = File(...),
    skip_duplicates: bool = True,
    user: User = Depends(RequireRole("APPROVER")),
    db: Session = Depends(get_db),
):
    from ..imports.service import execute_import
    content = await file.read()
    result = execute_import(content, entity_type, file.filename or "data.csv", db, skip_duplicates)
    AuthService(db).log_action(
        user.id, "IMPORT", entity_type,
        details={"imported": result["imported"], "skipped": result["skipped"]},
        ip_address=getattr(request.state, "client_ip", None),
    )
    return result


# ── Assignment ──────────────────────────────────────────

@router.post("/estimations/{estimation_id}/assign")
def assign_estimation(
    estimation_id: int,
    assigned_to_id: int,
    request: HTTPRequest,
    user: User = Depends(RequireRole("APPROVER")),
    db: Session = Depends(get_db),
):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    target_user = db.get(User, assigned_to_id)
    if not target_user:
        raise HTTPException(404, "Target user not found")
    estimation.assigned_to_id = assigned_to_id
    db.commit()

    # Notify assignee
    try:
        from ..notifications.service import NotificationService
        notifier = NotificationService(db)
        notifier.notify_user_assigned(
            estimation.estimation_number or f"EST-{estimation.id}",
            estimation.project_name,
            assigned_to_id,
            user.display_name,
        )
    except Exception:
        pass

    AuthService(db).log_action(user.id, "ASSIGN", "estimation", estimation_id, details={"assigned_to_id": assigned_to_id}, ip_address=getattr(request.state, "client_ip", None))
    return {"status": "ok", "assigned_to_id": assigned_to_id}


@router.post("/requests/{request_id}/assign")
def assign_request(
    request_id: int,
    assigned_to_id: int,
    request: HTTPRequest,
    user: User = Depends(RequireRole("APPROVER")),
    db: Session = Depends(get_db),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    target_user = db.get(User, assigned_to_id)
    if not target_user:
        raise HTTPException(404, "Target user not found")
    req.assigned_to_id = assigned_to_id
    db.commit()
    AuthService(db).log_action(user.id, "ASSIGN", "request", request_id, details={"assigned_to_id": assigned_to_id}, ip_address=getattr(request.state, "client_ip", None))

    # Task 10: Sync assignee to Redmine if request came from Redmine
    if req.request_source == "REDMINE" and req.external_id:
        try:
            from ..integrations.service import get_adapter
            adapter = get_adapter("REDMINE", db)
            if adapter and hasattr(adapter, "update_assignee"):
                adapter.update_assignee(req.external_id, target_user.username)
        except Exception:
            pass  # Don't break local assignment on Redmine sync failure

    return {"status": "ok", "assigned_to_id": assigned_to_id}


# ── Advanced Reports ────────────────────────────────────

@router.get("/estimations/{estimation_id}/report/executive-summary")
def download_executive_summary(estimation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..reports.executive_summary import ExecutiveSummaryData, generate_executive_summary
    data = ExecutiveSummaryData(
        project_name=estimation.project_name,
        estimation_number=estimation.estimation_number or "",
        project_type=estimation.project_type,
        created_by=estimation.created_by,
        created_at=str(estimation.created_at.date()) if estimation.created_at else "",
        grand_total_hours=estimation.grand_total_hours,
        grand_total_days=estimation.grand_total_days,
        feasibility_status=estimation.feasibility_status,
        total_tester_hours=estimation.total_tester_hours,
        total_leader_hours=estimation.total_leader_hours,
        dut_count=estimation.dut_count,
        profile_count=estimation.profile_count,
        dut_profile_combinations=estimation.dut_profile_combinations,
        tasks=[
            {"task_name": t.task_name, "task_type": t.task_type, "calculated_hours": t.calculated_hours}
            for t in estimation.tasks
        ],
    )
    content = generate_executive_summary(data)
    filename = f"{estimation.estimation_number or f'EST-{estimation_id}'}_summary.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reports/comparison")
def generate_comparison(
    estimation_a_id: int,
    estimation_b_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    est_a = db.get(Estimation, estimation_a_id)
    est_b = db.get(Estimation, estimation_b_id)
    if not est_a or not est_b:
        raise HTTPException(404, "One or both estimations not found")

    from ..reports.comparison_report import ComparisonReportData, generate_comparison_excel
    from ..reports.templates import ReportMetadata

    def _est_to_dict(est):
        return {
            "estimation_number": est.estimation_number,
            "project_name": est.project_name,
            "project_type": est.project_type,
            "grand_total_hours": est.grand_total_hours,
            "grand_total_days": est.grand_total_days,
            "total_tester_hours": est.total_tester_hours,
            "total_leader_hours": est.total_leader_hours,
            "feasibility_status": est.feasibility_status,
            "dut_count": est.dut_count,
            "profile_count": est.profile_count,
            "dut_profile_combinations": est.dut_profile_combinations,
            "pr_fix_count": est.pr_fix_count,
            "status": est.status,
            "tasks": [
                {"task_name": t.task_name, "task_type": t.task_type, "calculated_hours": t.calculated_hours}
                for t in est.tasks
            ],
        }

    data = ComparisonReportData(
        estimation_a=_est_to_dict(est_a),
        estimation_b=_est_to_dict(est_b),
    )
    content = generate_comparison_excel(data)
    filename = f"comparison_{est_a.estimation_number}_{est_b.estimation_number}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/trend")
def generate_trend(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..reports.trend_report import TrendReportData, generate_trend_excel

    projects = db.query(HistoricalProject).all()
    data = TrendReportData(
        projects=[
            {
                "project_name": p.project_name,
                "project_type": p.project_type,
                "estimated_hours": p.estimated_hours,
                "actual_hours": p.actual_hours,
                "dut_count": p.dut_count,
                "completion_date": str(p.completion_date) if p.completion_date else "",
            }
            for p in projects
        ]
    )
    content = generate_trend_excel(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="trend_analysis.xlsx"'},
    )


# ── Outline Wiki ────────────────────────────────────────

@router.post("/integrations/outline/publish/{estimation_id}")
def publish_to_outline(
    estimation_id: int,
    user: User = Depends(RequireRole("ESTIMATOR")),
    db: Session = Depends(get_db),
):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    from ..integrations.service import get_adapter
    adapter = get_adapter("OUTLINE", db)
    if not adapter:
        raise HTTPException(400, "Outline integration is not configured")

    from ..integrations.service import _estimation_to_export_dict
    est_data = _estimation_to_export_dict(estimation)

    # Enrich with additional data for comprehensive export
    _outline_wizard = json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {}

    # Add pr_no_test_hours
    est_data["pr_no_test_hours"] = getattr(estimation, "pr_no_test_hours", 0) or 0

    # Add working weeks and hours per day
    grand_total_days = estimation.grand_total_days or 0
    est_data["working_weeks"] = round(grand_total_days / 5.0, 1)
    est_data["working_hours_per_day"] = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    est_data["start_date"] = str(estimation.start_date) if estimation.start_date else ""
    est_data["testing_start_date"] = _outline_wizard.get("testing_start_date", "")
    est_data["expected_delivery"] = str(estimation.expected_delivery) if estimation.expected_delivery else ""

    # Add DUT/profile names
    dut_ids = _outline_wizard.get("dut_ids", [])
    profile_ids = _outline_wizard.get("profile_ids", [])
    if dut_ids:
        duts = db.query(DutType).filter(DutType.id.in_(dut_ids)).all()
        est_data["dut_names"] = [d.name for d in duts]
    if profile_ids:
        profiles = db.query(TestProfile).filter(TestProfile.id.in_(profile_ids)).all()
        est_data["profile_names"] = [p.name for p in profiles]

    # Add team allocation
    est_data["team_members"] = [
        {"name": a.team_member.name if a.team_member else "Unknown", "role": a.role or "", "allocated_hours": a.allocated_hours}
        for a in estimation.team_allocations
    ]

    # Add document deliverables
    doc_deliverables = _compute_doc_deliverables(estimation, db)
    est_data["document_deliverables"] = doc_deliverables

    # Add risk messages
    est_data["risk_messages"] = _build_risk_messages(estimation, db)

    # Add synthetic tasks (documentation + no-test PRs)
    tasks = est_data.get("tasks", [])
    tasks.extend(_build_doc_synthetic_tasks(doc_deliverables))
    pr_details = _outline_wizard.get("pr_details", [])
    pr_no_test_hrs_cfg = float(_get_config_value(db, "pr_no_test_hours", "8.0"))
    tasks.extend(_build_pr_no_test_synthetic_tasks(pr_details, pr_no_test_hrs_cfg))
    est_data["tasks"] = tasks

    result = adapter.export_estimation(est_data)
    return {
        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "errors": result.errors,
    }


@router.get("/integrations/outline/search")
def search_outline(
    query: str,
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..integrations.service import get_adapter
    adapter = get_adapter("OUTLINE", db)
    if not adapter:
        raise HTTPException(400, "Outline integration is not configured")
    return adapter.search_documents(query, limit)


# ── Teams (Task 7) ─────────────────────────────────────────────

@router.get("/teams", response_model=list[TeamOut])
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    result = []
    for t in teams:
        member_count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        result.append(TeamOut(
            id=t.id,
            name=t.name,
            description=t.description,
            created_at=t.created_at,
            member_count=member_count,
        ))
    return result


@router.post("/teams", response_model=TeamOut, status_code=201)
def create_team(data: TeamCreate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    existing = db.query(Team).filter(Team.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Team '{data.name}' already exists")
    team = Team(name=data.name, description=data.description)
    db.add(team)
    db.commit()
    db.refresh(team)
    return TeamOut(id=team.id, name=team.name, description=team.description, created_at=team.created_at, member_count=0)


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(team_id: int, data: TeamUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description
    db.commit()
    db.refresh(team)
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    return TeamOut(id=team.id, name=team.name, description=team.description, created_at=team.created_at, member_count=member_count)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    # Unlink members
    db.query(TeamMember).filter(TeamMember.team_id == team_id).update({"team_id": None})
    db.delete(team)
    db.commit()


@router.put("/teams/{team_id}/members")
def update_team_members(team_id: int, data: TeamMembersUpdate, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    # Remove current members from this team
    db.query(TeamMember).filter(TeamMember.team_id == team_id).update({"team_id": None})
    # Assign new members
    for mid in data.member_ids:
        member = db.get(TeamMember, mid)
        if member:
            member.team_id = team_id
    db.commit()
    return {"status": "ok", "team_id": team_id, "member_count": len(data.member_ids)}


# ── Task Presets (Task 4) ──────────────────────────────────────

@router.get("/task-presets", response_model=list[TaskPresetOut])
def list_task_presets(product_type: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TaskPreset)
    if product_type:
        q = q.filter(TaskPreset.product_type == product_type)
    presets = q.all()
    result = []
    for p in presets:
        ids = json.loads(p.task_template_ids_json) if p.task_template_ids_json else []
        result.append(TaskPresetOut(
            id=p.id,
            name=p.name,
            product_type=p.product_type,
            description=p.description,
            task_template_ids=ids,
            created_at=p.created_at,
        ))
    return result


@router.post("/task-presets", response_model=TaskPresetOut, status_code=201)
def create_task_preset(data: TaskPresetCreate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    existing = db.query(TaskPreset).filter(TaskPreset.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Preset '{data.name}' already exists")
    preset = TaskPreset(
        name=data.name,
        product_type=data.product_type,
        description=data.description,
        task_template_ids_json=json.dumps(data.task_template_ids),
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return TaskPresetOut(
        id=preset.id,
        name=preset.name,
        product_type=preset.product_type,
        description=preset.description,
        task_template_ids=data.task_template_ids,
        created_at=preset.created_at,
    )


@router.put("/task-presets/{preset_id}", response_model=TaskPresetOut)
def update_task_preset(preset_id: int, data: TaskPresetUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    preset = db.get(TaskPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Task preset not found")
    if data.name is not None:
        preset.name = data.name
    if data.product_type is not None:
        preset.product_type = data.product_type
    if data.description is not None:
        preset.description = data.description
    if data.task_template_ids is not None:
        preset.task_template_ids_json = json.dumps(data.task_template_ids)
    db.commit()
    db.refresh(preset)
    ids = json.loads(preset.task_template_ids_json) if preset.task_template_ids_json else []
    return TaskPresetOut(
        id=preset.id,
        name=preset.name,
        product_type=preset.product_type,
        description=preset.description,
        task_template_ids=ids,
        created_at=preset.created_at,
    )


@router.delete("/task-presets/{preset_id}", status_code=204)
def delete_task_preset(preset_id: int, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    preset = db.get(TaskPreset, preset_id)
    if not preset:
        raise HTTPException(404, "Task preset not found")
    db.delete(preset)
    db.commit()


# ── Risk Items ─────────────────────────────────────────────

@router.get("/risk-items", response_model=list[RiskItemOut])
def list_risk_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(RiskItem).filter(RiskItem.is_active.is_(True)).all()


@router.post("/risk-items", response_model=RiskItemOut, status_code=201)
def create_risk_item(data: RiskItemCreate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    existing = db.query(RiskItem).filter(RiskItem.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Risk item '{data.name}' already exists")
    item = RiskItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/risk-items/{item_id}", response_model=RiskItemOut)
def update_risk_item(item_id: int, data: RiskItemUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    item = db.get(RiskItem, item_id)
    if not item:
        raise HTTPException(404, "Risk item not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/risk-items/{item_id}", status_code=204)
def delete_risk_item(item_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    item = db.get(RiskItem, item_id)
    if not item:
        raise HTTPException(404, "Risk item not found")
    db.delete(item)
    db.commit()


# ── Document Types ─────────────────────────────────────────

def _doc_type_to_out(item: DocumentType) -> dict:
    """Convert DocumentType ORM to dict with resolved task_template_name."""
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "base_effort_hours": item.base_effort_hours,
        "is_active": item.is_active,
        "task_template_id": item.task_template_id,
        "task_template_name": item.task_template.name if item.task_template else None,
        "created_at": item.created_at,
    }


@router.get("/document-types", response_model=list[DocumentTypeOut])
def list_document_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(DocumentType).filter(DocumentType.is_active.is_(True)).order_by(DocumentType.name).all()
    return [_doc_type_to_out(i) for i in items]


@router.get("/document-types/all", response_model=list[DocumentTypeOut])
def list_all_document_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(DocumentType).order_by(DocumentType.name).all()
    return [_doc_type_to_out(i) for i in items]


@router.post("/document-types", response_model=DocumentTypeOut, status_code=201)
def create_document_type(data: DocumentTypeCreate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    existing = db.query(DocumentType).filter(DocumentType.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Document type '{data.name}' already exists")
    item = DocumentType(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _doc_type_to_out(item)


@router.put("/document-types/{item_id}", response_model=DocumentTypeOut)
def update_document_type(item_id: int, data: DocumentTypeUpdate, user: User = Depends(RequireRole("ESTIMATOR")), db: Session = Depends(get_db)):
    item = db.get(DocumentType, item_id)
    if not item:
        raise HTTPException(404, "Document type not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return _doc_type_to_out(item)


@router.delete("/document-types/{item_id}", status_code=204)
def delete_document_type(item_id: int, user: User = Depends(RequireRole("APPROVER")), db: Session = Depends(get_db)):
    item = db.get(DocumentType, item_id)
    if not item:
        raise HTTPException(404, "Document type not found")
    db.delete(item)
    db.commit()


# ── Snipe-IT Assets ────────────────────────────────────────

@router.get("/integrations/SNIPE_IT/assets")
def get_snipeit_assets(categories: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch hardware assets from Snipe-IT, optionally filtered by categories."""
    from ..integrations.service import get_adapter
    adapter = get_adapter("SNIPE_IT", db)
    if not adapter:
        raise HTTPException(400, "Snipe-IT integration is not configured or not enabled.")

    from ..integrations.snipeit_adapter import SnipeItAdapter
    if not isinstance(adapter, SnipeItAdapter):
        raise HTTPException(500, "Invalid Snipe-IT adapter")

    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    assets = adapter.get_hardware_by_category(cat_list)
    return assets


@router.get("/integrations/SNIPE_IT/categories")
def get_snipeit_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch available categories from Snipe-IT."""
    from ..integrations.service import get_adapter
    adapter = get_adapter("SNIPE_IT", db)
    if not adapter:
        raise HTTPException(400, "Snipe-IT integration is not configured or not enabled.")

    from ..integrations.snipeit_adapter import SnipeItAdapter
    if not isinstance(adapter, SnipeItAdapter):
        raise HTTPException(500, "Invalid Snipe-IT adapter")

    return adapter.get_categories()


# ── Jira Problem Reports (PR Items) ───────────────────────────

@router.get("/integrations/JIRA/pr-items")
def get_jira_pr_items(
    jql: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch PR / defect issues from Jira using a dedicated JQL query."""
    from ..integrations.service import get_adapter

    config = db.query(IntegrationConfig).filter_by(system_name="JIRA").first()
    if not config or not config.enabled:
        raise HTTPException(status_code=400, detail="JIRA integration not configured or not enabled.")

    adapter = get_adapter("JIRA", db)

    # Parse extra config for PR-specific settings
    import json as _json
    try:
        extra = _json.loads(config.additional_config_json or "{}")
    except Exception:
        extra = {}

    if not jql:
        jql = extra.get("pr_jql_filter", "")

    if not jql:
        raise HTTPException(status_code=400, detail="No PR JQL filter provided.")

    # Use separate PR API key if configured, otherwise fall back to main adapter key
    pr_api_key = extra.get("pr_api_key", "")

    try:
        import requests as http_requests

        # Build headers: use PR-specific API key if available
        if pr_api_key:
            import base64
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if adapter.is_cloud and adapter.username:
                creds = base64.b64encode(f"{adapter.username}:{pr_api_key}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"
            elif adapter.auth_mode == "basic" and adapter.username:
                creds = base64.b64encode(f"{adapter.username}:{pr_api_key}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"
            elif adapter.auth_mode == "pat":
                headers["Authorization"] = f"Bearer {pr_api_key}"
            elif adapter.username:
                creds = base64.b64encode(f"{adapter.username}:{pr_api_key}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"
            else:
                headers["Authorization"] = f"Bearer {pr_api_key}"

            resp = http_requests.request(
                "GET",
                adapter._url("search"),
                headers=headers,
                params={
                    "jql": jql,
                    "maxResults": 200,
                    "fields": "summary,priority,status,issuetype,created",
                },
                timeout=adapter.timeout,
                verify=adapter.ssl_verify,
            )
        else:
            resp = adapter._request(
                "GET",
                adapter._url("search"),
                params={
                    "jql": jql,
                    "maxResults": 200,
                    "fields": "summary,priority,status,issuetype,created",
                },
            )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])

        result = []
        for issue in issues:
            fields = issue.get("fields", {})
            priority = (fields.get("priority") or {}).get("name", "Medium")
            status = (fields.get("status") or {}).get("name", "")
            issue_type = (fields.get("issuetype") or {}).get("name", "")
            result.append({
                "key": issue.get("key", ""),
                "summary": fields.get("summary", ""),
                "priority": priority,
                "status": status,
                "issue_type": issue_type,
                "created": fields.get("created", ""),
            })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR items: {exc}")


# ── Estimation Version History & Diff ──────────────────────────────

@router.get("/estimations/{estimation_id}/versions")
def get_estimation_versions(
    estimation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all version snapshots for an estimation."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    snapshots = (
        db.query(EstimationVersionSnapshot)
        .filter(EstimationVersionSnapshot.estimation_id == estimation_id)
        .order_by(EstimationVersionSnapshot.version.asc())
        .all()
    )

    versions = []
    for snap in snapshots:
        data = json.loads(snap.snapshot_json)
        versions.append({
            "id": snap.id,
            "version": snap.version,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
            "project_name": data.get("project_name", ""),
            "grand_total_hours": data.get("grand_total_hours", 0),
            "feasibility_status": data.get("feasibility_status", ""),
            "status": data.get("status", ""),
        })

    # Add current version
    versions.append({
        "id": None,
        "version": estimation.version,
        "created_at": estimation.created_at.isoformat() if estimation.created_at else None,
        "project_name": estimation.project_name,
        "grand_total_hours": estimation.grand_total_hours,
        "feasibility_status": estimation.feasibility_status,
        "status": estimation.status,
        "is_current": True,
    })

    return versions


@router.get("/estimations/{estimation_id}/versions/{version_a}/diff/{version_b}")
def diff_estimation_versions(
    estimation_id: int,
    version_a: int,
    version_b: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare two versions of an estimation and return the differences."""
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")

    def _get_version_data(ver: int) -> dict:
        if ver == estimation.version:
            # Current version — build from live data
            return {
                "project_name": estimation.project_name,
                "project_type": estimation.project_type,
                "dut_count": estimation.dut_count,
                "profile_count": estimation.profile_count,
                "dut_profile_combinations": estimation.dut_profile_combinations,
                "pr_fix_count": estimation.pr_fix_count,
                "start_date": str(estimation.start_date) if estimation.start_date else None,
                "expected_delivery": str(estimation.expected_delivery) if estimation.expected_delivery else None,
                "total_tester_hours": estimation.total_tester_hours,
                "total_leader_hours": estimation.total_leader_hours,
                "pr_fix_hours": estimation.pr_fix_hours,
                "study_hours": estimation.study_hours,
                "buffer_hours": estimation.buffer_hours,
                "grand_total_hours": estimation.grand_total_hours,
                "grand_total_days": estimation.grand_total_days,
                "feasibility_status": estimation.feasibility_status,
                "status": estimation.status,
                "expected_releases": estimation.expected_releases,
                "release_extra_hours": getattr(estimation, "release_extra_hours", 0),
                "project_goals": estimation.project_goals,
                "target_customer": estimation.target_customer,
                "wizard_inputs": json.loads(estimation.wizard_inputs_json) if estimation.wizard_inputs_json else {},
                "tasks": [
                    {"task_name": t.task_name, "task_type": t.task_type, "base_hours": t.base_hours, "calculated_hours": t.calculated_hours}
                    for t in estimation.tasks
                ],
            }
        else:
            snap = (
                db.query(EstimationVersionSnapshot)
                .filter_by(estimation_id=estimation_id, version=ver)
                .first()
            )
            if not snap:
                raise HTTPException(404, f"Version {ver} snapshot not found")
            return json.loads(snap.snapshot_json)

    data_a = _get_version_data(version_a)
    data_b = _get_version_data(version_b)

    # Build diff — compare key fields
    diff_fields = [
        ("project_name", "Project Name"),
        ("project_type", "Project Type"),
        ("dut_count", "DUT Count"),
        ("profile_count", "Profile Count"),
        ("dut_profile_combinations", "DUT x Profile Combinations"),
        ("pr_fix_count", "PR Fix Count"),
        ("start_date", "Start Date"),
        ("expected_delivery", "Expected Delivery"),
        ("total_tester_hours", "Total Tester Hours"),
        ("total_leader_hours", "Total Leader Hours"),
        ("pr_fix_hours", "PR Fix Hours"),
        ("study_hours", "Study Hours"),
        ("buffer_hours", "Buffer Hours"),
        ("grand_total_hours", "Grand Total Hours"),
        ("grand_total_days", "Grand Total Days"),
        ("feasibility_status", "Feasibility"),
        ("expected_releases", "Expected Releases"),
        ("release_extra_hours", "Release Extra Hours"),
        ("project_goals", "Project Goals"),
        ("target_customer", "Target Customer"),
    ]

    changes = []
    for field_key, field_label in diff_fields:
        val_a = data_a.get(field_key)
        val_b = data_b.get(field_key)
        if val_a != val_b:
            changes.append({
                "field": field_label,
                "version_a": val_a,
                "version_b": val_b,
            })

    # Compare task lists
    tasks_a = data_a.get("tasks", [])
    tasks_b = data_b.get("tasks", [])
    tasks_a_names = {t["task_name"] for t in tasks_a}
    tasks_b_names = {t["task_name"] for t in tasks_b}
    added_tasks = [t for t in tasks_b if t["task_name"] not in tasks_a_names]
    removed_tasks = [t for t in tasks_a if t["task_name"] not in tasks_b_names]
    modified_tasks = []
    for tb in tasks_b:
        ta = next((t for t in tasks_a if t["task_name"] == tb["task_name"]), None)
        if ta and ta.get("calculated_hours") != tb.get("calculated_hours"):
            modified_tasks.append({
                "task_name": tb["task_name"],
                "hours_a": ta.get("calculated_hours", 0),
                "hours_b": tb.get("calculated_hours", 0),
            })

    # Compare wizard inputs (features, DUTs, profiles)
    wi_a = data_a.get("wizard_inputs", {})
    wi_b = data_b.get("wizard_inputs", {})
    input_changes = {}
    for wi_key in ["feature_ids", "new_feature_ids", "dut_ids", "profile_ids"]:
        list_a = set(wi_a.get(wi_key, []))
        list_b = set(wi_b.get(wi_key, []))
        if list_a != list_b:
            input_changes[wi_key] = {
                "added": sorted(list_b - list_a),
                "removed": sorted(list_a - list_b),
            }

    return {
        "estimation_id": estimation_id,
        "version_a": version_a,
        "version_b": version_b,
        "changes": changes,
        "added_tasks": added_tasks,
        "removed_tasks": removed_tasks,
        "modified_tasks": modified_tasks,
        "input_changes": input_changes,
    }


# ── Public Holidays ─────────────────────────────────────────────

@router.get("/public-holidays", response_model=list[PublicHolidayOut])
def list_public_holidays(
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all public holidays, optionally filtered by year."""
    from sqlalchemy import extract
    q = db.query(PublicHoliday)
    if year is not None:
        q = q.filter(
            (extract("year", PublicHoliday.date) == year) | (PublicHoliday.is_recurring == True)
        )
    return q.order_by(PublicHoliday.date).all()


@router.post("/public-holidays", response_model=PublicHolidayOut, status_code=201)
def create_public_holiday(
    data: PublicHolidayCreate,
    user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    holiday = PublicHoliday(
        date=data.date,
        name=data.name,
        country=data.country,
        is_recurring=data.is_recurring,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.put("/public-holidays/{holiday_id}", response_model=PublicHolidayOut)
def update_public_holiday(
    holiday_id: int,
    data: PublicHolidayUpdate,
    user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    holiday = db.get(PublicHoliday, holiday_id)
    if not holiday:
        raise HTTPException(404, "Holiday not found")
    if data.date is not None:
        holiday.date = data.date
    if data.name is not None:
        holiday.name = data.name
    if data.country is not None:
        holiday.country = data.country
    if data.is_recurring is not None:
        holiday.is_recurring = data.is_recurring
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/public-holidays/{holiday_id}")
def delete_public_holiday(
    holiday_id: int,
    user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    holiday = db.get(PublicHoliday, holiday_id)
    if not holiday:
        raise HTTPException(404, "Holiday not found")
    db.delete(holiday)
    db.commit()
    return {"detail": "Deleted"}


@router.post("/public-holidays/import-ics")
async def import_holidays_ics(
    file: UploadFile,
    user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    """Import public holidays from an ICS (iCalendar) file."""
    content = (await file.read()).decode("utf-8", errors="replace")

    imported = 0
    skipped = 0
    errors_list: list[str] = []

    # Simple ICS parser — extract VEVENT blocks
    events = content.split("BEGIN:VEVENT")
    for event_block in events[1:]:  # skip preamble before first VEVENT
        end_idx = event_block.find("END:VEVENT")
        if end_idx == -1:
            continue
        block = event_block[:end_idx]

        # Extract DTSTART
        event_date = None
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("DTSTART"):
                # Handle DTSTART;VALUE=DATE:20260101 and DTSTART:20260101T000000Z
                val = stripped.split(":", 1)[-1].strip()
                try:
                    event_date = date(int(val[:4]), int(val[4:6]), int(val[6:8]))
                except (ValueError, IndexError):
                    errors_list.append(f"Invalid date: {val}")
                break

        # Extract SUMMARY
        event_name = None
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("SUMMARY"):
                event_name = stripped.split(":", 1)[-1].strip()
                break

        if not event_date or not event_name:
            skipped += 1
            continue

        # Check for RRULE with YEARLY frequency → recurring
        is_recurring = "RRULE:" in block and "FREQ=YEARLY" in block

        # Skip duplicates (same date + name)
        existing = db.query(PublicHoliday).filter(
            PublicHoliday.date == event_date,
            PublicHoliday.name == event_name,
        ).first()
        if existing:
            skipped += 1
            continue

        db.add(PublicHoliday(
            date=event_date,
            name=event_name,
            country="",
            is_recurring=is_recurring,
        ))
        imported += 1

    db.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors_list,
    }


@router.get("/working-weeks")
def calculate_working_weeks(
    total_days: float,
    start_date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate working weeks from total days, excluding holidays.

    If start_date is provided, counts actual holidays in the period.
    Otherwise returns a simple conversion (total_days / 5).
    """
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))

    if start_date:
        from datetime import timedelta
        start = date.fromisoformat(start_date)
        # Walk forward through calendar days, counting working days
        remaining = total_days
        holidays = set()
        # Fetch all holidays
        all_holidays = db.query(PublicHoliday).all()
        for h in all_holidays:
            if h.is_recurring:
                # For recurring, match month and day across years
                for y in range(start.year, start.year + 3):
                    holidays.add(date(y, h.date.month, h.date.day))
            else:
                holidays.add(h.date)

        current = start
        working_days_counted = 0
        holiday_days_in_period = 0
        while remaining > 0:
            # Skip weekends
            if current.weekday() < 5:  # Mon-Fri
                if current in holidays:
                    holiday_days_in_period += 1
                else:
                    remaining -= 1
                    working_days_counted += 1
            current += timedelta(days=1)

        end_date = current - timedelta(days=1)
        calendar_days = (end_date - start).days + 1
        working_weeks = working_days_counted / 5.0

        return {
            "total_days": total_days,
            "working_days": working_days_counted,
            "working_weeks": round(working_weeks, 1),
            "holidays_excluded": holiday_days_in_period,
            "start_date": str(start),
            "end_date": str(end_date),
            "calendar_days": calendar_days,
        }
    else:
        working_weeks = total_days / 5.0
        return {
            "total_days": total_days,
            "working_days": total_days,
            "working_weeks": round(working_weeks, 1),
            "holidays_excluded": 0,
        }


# ── Backup & Restore ──────────────────────────────────


# Ordered by FK dependencies (parents before children)
_BACKUP_TABLES: list[tuple[str, type]] = [
    ("features", Feature),
    ("task_templates", TaskTemplate),
    ("task_template_features", TaskTemplateFeature),
    ("dut_types", DutType),
    ("test_profiles", TestProfile),
    ("team_members", TeamMember),
    ("risk_items", RiskItem),
    ("document_types", DocumentType),
    ("public_holidays", PublicHoliday),
]


def _row_to_dict(row) -> dict:
    """Convert an ORM row to a plain dict, serializing dates/datetimes."""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, (date, datetime)):
            val = val.isoformat()
        d[col.name] = val
    return d


@router.get("/admin/backup")
def admin_backup(
    request: HTTPRequest,
    current_user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    """Export all config data as a downloadable JSON file."""
    tables_data: dict[str, list[dict]] = {}
    tables_count: dict[str, int] = {}
    for table_name, model_cls in _BACKUP_TABLES:
        rows = db.query(model_cls).all()
        serialized = [_row_to_dict(r) for r in rows]
        tables_data[table_name] = serialized
        tables_count[table_name] = len(serialized)

    backup = {
        "version": "3.4.0",
        "timestamp": datetime.utcnow().isoformat(),
        "tables": tables_data,
    }

    auth_service = AuthService(db)
    client_ip = getattr(request.state, "client_ip", None)
    auth_service.log_action(
        user_id=current_user.id,
        action="BACKUP",
        resource_type="system",
        details={"tables": tables_count},
        ip_address=client_ip,
    )

    content = json.dumps(backup, indent=2, default=str)
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="presto_backup_{timestamp_str}.json"'
        },
    )


@router.post("/admin/restore")
def admin_restore(
    request: HTTPRequest,
    file: UploadFile = File(...),
    current_user: User = Depends(RequireRole("ADMIN")),
    db: Session = Depends(get_db),
):
    """Restore config data from a backup JSON file."""
    try:
        raw = file.file.read()
        backup = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}")

    if "tables" not in backup:
        raise HTTPException(status_code=400, detail="Invalid backup format: missing 'tables' key")

    tables_map = backup["tables"]
    tables_restored: list[str] = []
    rows_restored: dict[str, int] = {}

    try:
        # Delete in reverse order (children before parents) to respect FK constraints
        for table_name, model_cls in reversed(_BACKUP_TABLES):
            if table_name in tables_map:
                db.query(model_cls).delete()

        db.flush()

        # Insert in forward order (parents before children)
        for table_name, model_cls in _BACKUP_TABLES:
            if table_name not in tables_map:
                continue
            rows = tables_map[table_name]
            for row_data in rows:
                # Convert date strings back to date objects for date columns
                for col in model_cls.__table__.columns:
                    col_name = col.name
                    if col_name in row_data and row_data[col_name] is not None:
                        col_type = str(col.type)
                        if "DATE" in col_type and not "DATETIME" in col_type:
                            try:
                                row_data[col_name] = date.fromisoformat(row_data[col_name])
                            except (ValueError, TypeError):
                                pass
                        elif "DATETIME" in col_type:
                            try:
                                row_data[col_name] = datetime.fromisoformat(row_data[col_name])
                            except (ValueError, TypeError):
                                pass
                obj = model_cls(**row_data)
                db.add(obj)
            tables_restored.append(table_name)
            rows_restored[table_name] = len(rows)

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}")

    auth_service = AuthService(db)
    client_ip = getattr(request.state, "client_ip", None)
    auth_service.log_action(
        user_id=current_user.id,
        action="RESTORE",
        resource_type="system",
        details={"tables_restored": tables_restored, "rows_restored": rows_restored},
        ip_address=client_ip,
    )

    return {
        "status": "ok",
        "tables_restored": tables_restored,
        "rows_restored": rows_restored,
    }
