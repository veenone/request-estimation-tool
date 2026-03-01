"""JSON stdin/stdout IPC handler for C# subprocess communication.

Reads JSON commands from stdin, dispatches to the appropriate handler,
and writes JSON responses to stdout.

Protocol:
  Input:  {"command": "...", "payload": {...}, "token": "eyJ..."}
  Output: {"status": "ok"|"error", "result": {...}} or {"status": "error", "message": "..."}

v2.0: Added token-based authentication. Write commands require a valid JWT.
"""

import base64
import json
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..database.migrations import init_database
from ..database.engine import get_engine
from ..database.models import (
    Configuration,
    DutType,
    Estimation,
    EstimationTask,
    Feature,
    HistoricalProject,
    IntegrationConfig,
    Request,
    TaskTemplate,
    TeamMember,
    TestProfile,
)
from ..auth.models import AuditLog, User
from ..auth.service import AuthService
from ..engine.calculator import (
    EstimationInput,
    PRFixInput,
    TaskInput,
    calculate_estimation,
)
from ..engine.calibration import HistoricalDataPoint, calibrate
from ..engine.feasibility import assess_risks


def _get_session(db_path: str | None = None) -> Session:
    engine = get_engine(db_path)
    return Session(engine)


def _get_config(session: Session, key: str, default: str) -> str:
    cfg = session.query(Configuration).filter(Configuration.key == key).first()
    return cfg.value if cfg else default


def _generate_number(session: Session, prefix_key: str, table_class: type) -> str:
    prefix = _get_config(session, prefix_key, "EST")
    year = datetime.now().year
    count = session.query(table_class).count()
    return f"{prefix}-{year}-{count + 1:03d}"


# ── Authentication ──────────────────────────────────────


def _validate_token(session: Session, token: str | None) -> User | None:
    """Validate JWT token and return User or None."""
    if not token:
        return None
    auth_service = AuthService(session)
    payload = auth_service.validate_access_token(token)
    if not payload:
        return None
    return auth_service.get_user_by_id(int(payload["sub"]))


def handle_login(session: Session, payload: dict) -> dict:
    """Authenticate user and return JWT tokens."""
    username = payload.get("username", "")
    password = payload.get("password", "")

    auth_service = AuthService(session)
    result = auth_service.login(username, password)

    # Try LDAP if local fails
    if result is None:
        try:
            from ..auth.ldap_provider import LDAPProvider
            ldap = LDAPProvider(session)
            if ldap.is_configured:
                ldap_user = ldap.authenticate(username, password)
                if ldap_user:
                    access_token = auth_service.create_access_token(ldap_user)
                    refresh_token = auth_service.create_refresh_token(ldap_user)
                    result = (ldap_user, access_token, refresh_token)
        except Exception:
            pass

    if result is None:
        raise ValueError("Invalid username or password")

    user, access_token, refresh_token = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "auth_provider": user.auth_provider,
            "is_active": user.is_active,
        },
    }


def handle_refresh_token(session: Session, payload: dict) -> dict:
    auth_service = AuthService(session)
    result = auth_service.refresh(payload.get("refresh_token", ""))
    if result is None:
        raise ValueError("Invalid or expired refresh token")
    user, access_token, new_refresh = result
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
    }


def handle_logout(session: Session, payload: dict) -> dict:
    auth_service = AuthService(session)
    auth_service.logout(payload.get("refresh_token", ""))
    return {"logged_out": True}


def handle_validate_session(session: Session, payload: dict) -> dict:
    """Validate a token and return user info."""
    token = payload.get("token", "")
    user = _validate_token(session, token)
    if not user:
        raise ValueError("Invalid or expired token")
    return {
        "valid": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "auth_provider": user.auth_provider,
            "is_active": user.is_active,
        },
    }


def handle_get_current_user(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user:
        raise ValueError("Authentication required")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "auth_provider": user.auth_provider,
        "is_active": user.is_active,
        "team_member_id": user.team_member_id,
        "last_login_at": str(user.last_login_at) if user.last_login_at else None,
    }


def handle_change_password(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user:
        raise ValueError("Authentication required")
    auth_service = AuthService(session)
    if not auth_service.change_password(
        user.id, payload["current_password"], payload["new_password"]
    ):
        raise ValueError("Current password is incorrect")
    return {"changed": True}


# ── Users (ADMIN only) ─────────────────────────────────


def handle_get_users(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "ADMIN"):
        raise ValueError("Admin access required")
    auth_service = AuthService(session)
    users = auth_service.list_users(active_only=payload.get("active_only", False))
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "auth_provider": u.auth_provider,
                "is_active": u.is_active,
                "team_member_id": u.team_member_id,
                "last_login_at": str(u.last_login_at) if u.last_login_at else None,
                "created_at": str(u.created_at) if u.created_at else None,
            }
            for u in users
        ]
    }


def handle_create_user(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "ADMIN"):
        raise ValueError("Admin access required")
    auth_service = AuthService(session)
    existing = auth_service.get_user_by_username(payload["username"])
    if existing:
        raise ValueError(f"Username '{payload['username']}' already exists")
    new_user = auth_service.create_user(
        username=payload["username"],
        display_name=payload["display_name"],
        password=payload.get("password"),
        email=payload.get("email"),
        role=payload.get("role", "VIEWER"),
        auth_provider=payload.get("auth_provider", "local"),
        team_member_id=payload.get("team_member_id"),
    )
    auth_service.log_action(user.id, "CREATE", "user", new_user.id)
    return {"id": new_user.id, "username": new_user.username}


def handle_update_user(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "ADMIN"):
        raise ValueError("Admin access required")
    auth_service = AuthService(session)
    kwargs = {}
    for key in ("email", "display_name", "role", "is_active", "team_member_id", "password"):
        if key in payload and key != "id":
            kwargs[key] = payload[key]
    updated = auth_service.update_user(payload["id"], **kwargs)
    if not updated:
        raise ValueError(f"User {payload['id']} not found")
    auth_service.log_action(user.id, "UPDATE", "user", payload["id"])
    return {"id": updated.id, "username": updated.username}


def handle_delete_user(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "ADMIN"):
        raise ValueError("Admin access required")
    if payload["id"] == user.id:
        raise ValueError("Cannot delete your own account")
    auth_service = AuthService(session)
    if not auth_service.delete_user(payload["id"]):
        raise ValueError(f"User {payload['id']} not found")
    auth_service.log_action(user.id, "DELETE", "user", payload["id"])
    return {"deleted": True}


# ── Audit Log ───────────────────────────────────────────


def handle_get_audit_log(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "APPROVER"):
        raise ValueError("Approver access required")
    auth_service = AuthService(session)
    logs = auth_service.get_audit_log(
        limit=payload.get("limit", 100),
        offset=payload.get("offset", 0),
        action=payload.get("action"),
        resource_type=payload.get("resource_type"),
    )
    return {
        "entries": [
            {
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
            for log in logs
        ]
    }


# ── Features ─────────────────────────────────────────────


def handle_get_features(session: Session, payload: dict) -> dict:
    features = session.query(Feature).all()
    return {
        "features": [
            {
                "id": f.id,
                "name": f.name,
                "category": f.category,
                "complexity_weight": f.complexity_weight,
                "has_existing_tests": f.has_existing_tests,
                "description": f.description,
                "task_templates": [
                    {
                        "id": t.id,
                        "feature_id": t.feature_id,
                        "name": t.name,
                        "task_type": t.task_type,
                        "base_effort_hours": t.base_effort_hours,
                        "scales_with_dut": t.scales_with_dut,
                        "scales_with_profile": t.scales_with_profile,
                        "is_parallelizable": t.is_parallelizable,
                    }
                    for t in f.task_templates
                ],
            }
            for f in features
        ]
    }


def handle_create_feature(session: Session, payload: dict) -> dict:
    feature = Feature(
        name=payload["name"],
        category=payload.get("category"),
        complexity_weight=payload.get("complexity_weight", 1.0),
        has_existing_tests=payload.get("has_existing_tests", False),
        description=payload.get("description"),
    )
    session.add(feature)
    session.commit()
    session.refresh(feature)
    return {"id": feature.id, "name": feature.name}


def handle_update_feature(session: Session, payload: dict) -> dict:
    feature = session.get(Feature, payload["id"])
    if not feature:
        raise ValueError(f"Feature {payload['id']} not found")
    for key in ("name", "category", "complexity_weight", "has_existing_tests", "description"):
        if key in payload:
            setattr(feature, key, payload[key])
    session.commit()
    return {"id": feature.id, "name": feature.name}


def handle_delete_feature(session: Session, payload: dict) -> dict:
    feature = session.get(Feature, payload["id"])
    if not feature:
        raise ValueError(f"Feature {payload['id']} not found")
    session.delete(feature)
    session.commit()
    return {"deleted": True}


# ── DUT Types ────────────────────────────────────────────


def handle_get_dut_types(session: Session, payload: dict) -> dict:
    duts = session.query(DutType).all()
    return {
        "dut_types": [
            {"id": d.id, "name": d.name, "category": d.category, "complexity_multiplier": d.complexity_multiplier}
            for d in duts
        ]
    }


def handle_create_dut_type(session: Session, payload: dict) -> dict:
    dut = DutType(
        name=payload["name"],
        category=payload.get("category"),
        complexity_multiplier=payload.get("complexity_multiplier", 1.0),
    )
    session.add(dut)
    session.commit()
    session.refresh(dut)
    return {"id": dut.id, "name": dut.name}


def handle_update_dut_type(session: Session, payload: dict) -> dict:
    dut = session.get(DutType, payload["id"])
    if not dut:
        raise ValueError(f"DUT type {payload['id']} not found")
    for key in ("name", "category", "complexity_multiplier"):
        if key in payload:
            setattr(dut, key, payload[key])
    session.commit()
    return {"id": dut.id, "name": dut.name}


def handle_delete_dut_type(session: Session, payload: dict) -> dict:
    dut = session.get(DutType, payload["id"])
    if not dut:
        raise ValueError(f"DUT type {payload['id']} not found")
    session.delete(dut)
    session.commit()
    return {"deleted": True}


# ── Test Profiles ────────────────────────────────────────


def handle_get_profiles(session: Session, payload: dict) -> dict:
    profiles = session.query(TestProfile).all()
    return {
        "profiles": [
            {"id": p.id, "name": p.name, "description": p.description, "effort_multiplier": p.effort_multiplier}
            for p in profiles
        ]
    }


def handle_create_profile(session: Session, payload: dict) -> dict:
    profile = TestProfile(
        name=payload["name"],
        description=payload.get("description"),
        effort_multiplier=payload.get("effort_multiplier", 1.0),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return {"id": profile.id, "name": profile.name}


def handle_update_profile(session: Session, payload: dict) -> dict:
    profile = session.get(TestProfile, payload["id"])
    if not profile:
        raise ValueError(f"Profile {payload['id']} not found")
    for key in ("name", "description", "effort_multiplier"):
        if key in payload:
            setattr(profile, key, payload[key])
    session.commit()
    return {"id": profile.id, "name": profile.name}


def handle_delete_profile(session: Session, payload: dict) -> dict:
    profile = session.get(TestProfile, payload["id"])
    if not profile:
        raise ValueError(f"Profile {payload['id']} not found")
    session.delete(profile)
    session.commit()
    return {"deleted": True}


# ── Team Members ─────────────────────────────────────────


def handle_get_team_members(session: Session, payload: dict) -> dict:
    members = session.query(TeamMember).all()
    return {
        "team_members": [
            {
                "id": m.id,
                "name": m.name,
                "role": m.role,
                "available_hours_per_day": m.available_hours_per_day,
                "skills_json": m.skills_json,
            }
            for m in members
        ]
    }


def handle_create_team_member(session: Session, payload: dict) -> dict:
    member = TeamMember(
        name=payload["name"],
        role=payload["role"],
        available_hours_per_day=payload.get("available_hours_per_day", 7.0),
        skills_json=payload.get("skills_json", "[]"),
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return {"id": member.id, "name": member.name}


def handle_update_team_member(session: Session, payload: dict) -> dict:
    member = session.get(TeamMember, payload["id"])
    if not member:
        raise ValueError(f"Team member {payload['id']} not found")
    for key in ("name", "role", "available_hours_per_day", "skills_json"):
        if key in payload:
            setattr(member, key, payload[key])
    session.commit()
    return {"id": member.id, "name": member.name}


def handle_delete_team_member(session: Session, payload: dict) -> dict:
    member = session.get(TeamMember, payload["id"])
    if not member:
        raise ValueError(f"Team member {payload['id']} not found")
    session.delete(member)
    session.commit()
    return {"deleted": True}


# ── Historical Projects ──────────────────────────────────


def handle_get_historical_projects(session: Session, payload: dict) -> dict:
    projects = session.query(HistoricalProject).all()
    return {
        "projects": [
            {
                "id": p.id,
                "project_name": p.project_name,
                "project_type": p.project_type,
                "estimated_hours": p.estimated_hours,
                "actual_hours": p.actual_hours,
                "dut_count": p.dut_count,
                "profile_count": p.profile_count,
                "pr_count": p.pr_count,
                "features_json": p.features_json,
                "completion_date": str(p.completion_date) if p.completion_date else None,
                "notes": p.notes,
            }
            for p in projects
        ]
    }


def handle_create_historical_project(session: Session, payload: dict) -> dict:
    proj = HistoricalProject(
        project_name=payload["project_name"],
        project_type=payload["project_type"],
        estimated_hours=payload.get("estimated_hours"),
        actual_hours=payload.get("actual_hours"),
        dut_count=payload.get("dut_count"),
        profile_count=payload.get("profile_count"),
        pr_count=payload.get("pr_count"),
        features_json=payload.get("features_json", "[]"),
        completion_date=date.fromisoformat(payload["completion_date"]) if payload.get("completion_date") else None,
        notes=payload.get("notes"),
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return {"id": proj.id, "project_name": proj.project_name}


# ── Requests ─────────────────────────────────────────────


def handle_get_requests(session: Session, payload: dict) -> dict:
    q = session.query(Request)
    status = payload.get("status")
    if status:
        q = q.filter(Request.status == status)
    requests = q.order_by(Request.created_at.desc()).all()
    return {
        "requests": [
            {
                "id": r.id,
                "request_number": r.request_number,
                "request_source": r.request_source,
                "external_id": r.external_id,
                "title": r.title,
                "description": r.description,
                "requester_name": r.requester_name,
                "requester_email": r.requester_email,
                "business_unit": r.business_unit,
                "priority": r.priority,
                "status": r.status,
                "requested_delivery_date": str(r.requested_delivery_date) if r.requested_delivery_date else None,
                "received_date": str(r.received_date) if r.received_date else None,
                "assigned_to_id": r.assigned_to_id,
                "notes": r.notes,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in requests
        ]
    }


def handle_create_request(session: Session, payload: dict) -> dict:
    req_number = payload["request_number"]
    req = Request(
        request_number=req_number,
        request_source=payload.get("request_source", "MANUAL"),
        external_id=payload.get("external_id"),
        title=payload["title"],
        description=payload.get("description"),
        requester_name=payload["requester_name"],
        requester_email=payload.get("requester_email"),
        business_unit=payload.get("business_unit"),
        priority=payload.get("priority", "MEDIUM"),
        requested_delivery_date=(
            date.fromisoformat(payload["requested_delivery_date"])
            if payload.get("requested_delivery_date")
            else None
        ),
        received_date=date.fromisoformat(payload.get("received_date", date.today().isoformat())),
        notes=payload.get("notes"),
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return {"id": req.id, "request_number": req.request_number}


def handle_update_request(session: Session, payload: dict) -> dict:
    req = session.get(Request, payload["id"])
    if not req:
        raise ValueError(f"Request {payload['id']} not found")
    for key in ("title", "description", "requester_name", "requester_email",
                "business_unit", "priority", "status", "notes"):
        if key in payload:
            setattr(req, key, payload[key])
    if "requested_delivery_date" in payload:
        val = payload["requested_delivery_date"]
        req.requested_delivery_date = date.fromisoformat(val) if val else None
    if "assigned_to_id" in payload:
        req.assigned_to_id = payload["assigned_to_id"]
    session.commit()
    return {"id": req.id, "request_number": req.request_number}


# ── Estimations ──────────────────────────────────────────


def handle_get_estimations(session: Session, payload: dict) -> dict:
    estimations = session.query(Estimation).order_by(Estimation.created_at.desc()).all()
    return {
        "estimations": [
            {
                "id": e.id,
                "request_id": e.request_id,
                "estimation_number": e.estimation_number,
                "project_name": e.project_name,
                "project_type": e.project_type,
                "dut_count": e.dut_count,
                "profile_count": e.profile_count,
                "dut_profile_combinations": e.dut_profile_combinations,
                "pr_fix_count": e.pr_fix_count,
                "expected_delivery": str(e.expected_delivery) if e.expected_delivery else None,
                "total_tester_hours": e.total_tester_hours,
                "total_leader_hours": e.total_leader_hours,
                "grand_total_hours": e.grand_total_hours,
                "grand_total_days": e.grand_total_days,
                "feasibility_status": e.feasibility_status,
                "status": e.status,
                "created_at": str(e.created_at) if e.created_at else None,
                "created_by": e.created_by,
                "approved_by": e.approved_by,
                "approved_at": str(e.approved_at) if e.approved_at else None,
                "assigned_to_id": e.assigned_to_id,
            }
            for e in estimations
        ]
    }


def handle_get_estimation(session: Session, payload: dict) -> dict:
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")
    req = session.get(Request, est.request_id) if est.request_id else None

    return {
        "id": est.id,
        "request_id": est.request_id,
        "request_source": req.request_source if req else None,
        "external_id": req.external_id if req else None,
        "estimation_number": est.estimation_number,
        "project_name": est.project_name,
        "project_type": est.project_type,
        "reference_project_ids": est.reference_project_ids,
        "dut_count": est.dut_count,
        "profile_count": est.profile_count,
        "dut_profile_combinations": est.dut_profile_combinations,
        "pr_fix_count": est.pr_fix_count,
        "expected_delivery": str(est.expected_delivery) if est.expected_delivery else None,
        "total_tester_hours": est.total_tester_hours,
        "total_leader_hours": est.total_leader_hours,
        "grand_total_hours": est.grand_total_hours,
        "grand_total_days": est.grand_total_days,
        "feasibility_status": est.feasibility_status,
        "status": est.status,
        "created_at": str(est.created_at) if est.created_at else None,
        "created_by": est.created_by,
        "approved_by": est.approved_by,
        "approved_at": str(est.approved_at) if est.approved_at else None,
        "assigned_to_id": est.assigned_to_id,
        "tasks": [
            {
                "id": t.id,
                "task_template_id": t.task_template_id,
                "task_name": t.task_name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "calculated_hours": t.calculated_hours,
                "assigned_testers": t.assigned_testers,
                "has_leader_support": t.has_leader_support,
                "leader_hours": t.leader_hours,
                "is_new_feature_study": t.is_new_feature_study,
                "notes": t.notes,
            }
            for t in est.tasks
        ],
    }


def handle_save_estimation(session: Session, payload: dict) -> dict:
    """Save a new estimation from wizard results."""
    leader_ratio = float(_get_config(session, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config(session, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config(session, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config(session, "buffer_percentage", "10"))

    feature_ids = payload.get("feature_ids", [])
    new_feature_ids = payload.get("new_feature_ids", [])

    features = session.query(Feature).filter(Feature.id.in_(feature_ids)).all() if feature_ids else []
    templates = (
        session.query(TaskTemplate)
        .filter((TaskTemplate.feature_id.in_(feature_ids)) | (TaskTemplate.feature_id.is_(None)))
        .all()
        if feature_ids
        else session.query(TaskTemplate).filter(TaskTemplate.feature_id.is_(None)).all()
    )

    task_inputs: list[TaskInput] = []
    for tmpl in templates:
        feat = next((f for f in features if f.id == tmpl.feature_id), None)
        cw = feat.complexity_weight if feat else 1.0
        task_inputs.append(
            TaskInput(
                name=tmpl.name,
                task_type=tmpl.task_type,
                base_effort_hours=tmpl.base_effort_hours,
                scales_with_dut=tmpl.scales_with_dut,
                scales_with_profile=tmpl.scales_with_profile,
                complexity_weight=cw,
                is_new_feature_study=tmpl.feature_id in new_feature_ids if tmpl.feature_id else False,
                template_id=tmpl.id,
            )
        )

    dut_ids = payload.get("dut_ids", [])
    profile_ids = payload.get("profile_ids", [])
    dut_count = len(dut_ids) or 1
    profile_count = len(profile_ids) or 1
    matrix = payload.get("dut_profile_matrix", [])
    combinations = len(matrix) if matrix else dut_count * profile_count

    pr_data = payload.get("pr_fixes", {})
    pr_total = pr_data.get("simple", 0) + pr_data.get("medium", 0) + pr_data.get("complex", 0)

    calc_input = EstimationInput(
        project_type=payload.get("project_type", "NEW"),
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        pr_fixes=PRFixInput(
            simple=pr_data.get("simple", 0),
            medium=pr_data.get("medium", 0),
            complex=pr_data.get("complex", 0),
        ),
        new_feature_count=len(new_feature_ids),
        team_size=payload.get("team_size", 1),
        has_leader=payload.get("has_leader", False),
        working_days=payload.get("working_days", 20),
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
    )
    result = calculate_estimation(calc_input)

    est_number = _generate_number(session, "estimation_number_prefix", Estimation)

    estimation = Estimation(
        request_id=payload.get("request_id"),
        estimation_number=est_number,
        project_name=payload.get("project_name", "Untitled"),
        project_type=payload.get("project_type", "NEW"),
        reference_project_ids=json.dumps(payload.get("reference_project_ids", [])),
        dut_count=dut_count,
        profile_count=profile_count,
        dut_profile_combinations=combinations,
        pr_fix_count=pr_total,
        expected_delivery=(
            date.fromisoformat(payload["expected_delivery"]) if payload.get("expected_delivery") else None
        ),
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        grand_total_hours=result.grand_total_hours,
        grand_total_days=result.grand_total_days,
        feasibility_status=result.feasibility_status,
        status="DRAFT",
        created_by=payload.get("created_by"),
        created_by_id=payload.get("created_by_id"),
        assigned_to_id=payload.get("assigned_to_id"),
    )
    session.add(estimation)
    session.flush()

    has_leader = payload.get("has_leader", False)
    for task in result.tasks:
        et = EstimationTask(
            estimation_id=estimation.id,
            task_template_id=task.template_id,
            task_name=task.name,
            task_type=task.task_type,
            base_hours=task.base_hours,
            calculated_hours=task.calculated_hours,
            assigned_testers=1,
            has_leader_support=has_leader,
            leader_hours=task.calculated_hours * leader_ratio if has_leader else 0,
            is_new_feature_study=task.is_new_feature_study,
        )
        session.add(et)

    # Update request status if linked
    if payload.get("request_id"):
        req = session.get(Request, payload["request_id"])
        if req:
            req.status = "ESTIMATED"

    session.commit()
    session.refresh(estimation)
    return {"id": estimation.id, "estimation_number": estimation.estimation_number}


def handle_update_estimation_status(session: Session, payload: dict) -> dict:
    """Update estimation status following workflow: DRAFT -> FINAL -> APPROVED."""
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")

    valid_transitions = {
        "DRAFT": ["FINAL", "REVISED"],
        "FINAL": ["APPROVED", "REVISED"],
        "APPROVED": ["REVISED"],
        "REVISED": ["DRAFT"],
    }

    old_status = est.status
    target = payload["status"]
    allowed = valid_transitions.get(est.status, [])
    if target not in allowed:
        raise ValueError(f"Invalid transition: {est.status} -> {target}. Allowed: {allowed}")

    est.status = target
    if target == "APPROVED":
        est.approved_by = payload.get("approved_by")
        est.approved_by_id = payload.get("approved_by_id")
        est.approved_at = datetime.now()
    elif target == "REVISED":
        est.approved_by = None
        est.approved_by_id = None
        est.approved_at = None

    session.commit()

    # Auto-export to external system when estimation is finalized or approved
    if target in ("FINAL", "APPROVED") and est.request_id:
        _try_export_estimation(est, session)

    # Send notification
    try:
        from ..notifications.service import NotificationService
        notifier = NotificationService(session)
        notifier.notify_estimation_status_changed(
            est.estimation_number or f"EST-{est.id}",
            est.project_name,
            old_status,
            target,
            payload.get("changed_by", "System"),
            est.grand_total_hours,
            creator_user_id=est.created_by_id,
            assigned_user_id=est.assigned_to_id,
        )
    except Exception:
        pass

    return {"id": est.id, "status": est.status}


def _try_export_estimation(estimation: Estimation, session: Session) -> None:
    """Attempt to export estimation results back to the originating external system."""
    req = session.get(Request, estimation.request_id)
    if not req or not req.external_id or req.request_source == "MANUAL":
        return

    try:
        from ..integrations.service import sync_export

        estimation_data = {
            "external_id": req.external_id,
            "grand_total_hours": estimation.grand_total_hours,
            "feasibility_status": estimation.feasibility_status,
            "estimation_number": estimation.estimation_number or f"EST-{estimation.id}",
        }
        sync_export(req.request_source, estimation_data, session)
    except Exception:
        pass


def handle_export_estimation(session: Session, payload: dict) -> dict:
    """Manually export estimation results to the linked external system."""
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")
    if not est.request_id:
        raise ValueError("Estimation is not linked to a request")

    req = session.get(Request, est.request_id)
    if not req or not req.external_id:
        raise ValueError("Linked request has no external ID")
    if req.request_source == "MANUAL":
        raise ValueError("Request source is MANUAL — no external system to export to")

    from ..integrations.service import sync_export

    estimation_data = {
        "external_id": req.external_id,
        "grand_total_hours": est.grand_total_hours,
        "feasibility_status": est.feasibility_status,
        "estimation_number": est.estimation_number or f"EST-{est.id}",
    }
    result = sync_export(req.request_source, estimation_data, session)

    return {
        "status": result.status.value,
        "system": result.system,
        "items_updated": result.items_updated,
        "errors": result.errors,
    }


# ── Assignment ──────────────────────────────────────────


def handle_assign_estimation(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "APPROVER"):
        raise ValueError("Approver access required")
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")
    target_user = session.get(User, payload["assigned_to_id"])
    if not target_user:
        raise ValueError(f"User {payload['assigned_to_id']} not found")
    est.assigned_to_id = payload["assigned_to_id"]
    session.commit()

    # Notify assignee
    try:
        from ..notifications.service import NotificationService
        notifier = NotificationService(session)
        notifier.notify_user_assigned(
            est.estimation_number or f"EST-{est.id}",
            est.project_name,
            payload["assigned_to_id"],
            user.display_name,
        )
    except Exception:
        pass

    AuthService(session).log_action(
        user.id, "ASSIGN", "estimation", est.id,
        details={"assigned_to_id": payload["assigned_to_id"]},
    )
    return {"id": est.id, "assigned_to_id": est.assigned_to_id}


def handle_assign_request(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "APPROVER"):
        raise ValueError("Approver access required")
    req = session.get(Request, payload["id"])
    if not req:
        raise ValueError(f"Request {payload['id']} not found")
    req.assigned_to_id = payload["assigned_to_id"]
    session.commit()
    AuthService(session).log_action(
        user.id, "ASSIGN", "request", req.id,
        details={"assigned_to_id": payload["assigned_to_id"]},
    )
    return {"id": req.id, "assigned_to_id": req.assigned_to_id}


# ── Configuration ────────────────────────────────────────


def handle_get_configuration(session: Session, payload: dict) -> dict:
    configs = session.query(Configuration).all()
    return {key_val.key: key_val.value for key_val in configs}


def handle_set_configuration(session: Session, payload: dict) -> dict:
    key = payload["key"]
    value = payload["value"]
    cfg = session.query(Configuration).filter(Configuration.key == key).first()
    if cfg:
        cfg.value = str(value)
    else:
        session.add(Configuration(key=key, value=str(value)))
    session.commit()
    return {"key": key, "value": str(value)}


# ── Dashboard ────────────────────────────────────────────


def handle_get_dashboard_stats(session: Session, payload: dict) -> dict:
    total_requests = session.query(Request).count()
    requests_new = session.query(Request).filter(Request.status == "NEW").count()
    requests_in_progress = session.query(Request).filter(
        Request.status.in_(["IN_ESTIMATION", "IN_PROGRESS"])
    ).count()
    requests_completed = session.query(Request).filter(Request.status == "COMPLETED").count()

    total_estimations = session.query(Estimation).count()
    estimations_draft = session.query(Estimation).filter(Estimation.status == "DRAFT").count()
    estimations_final = session.query(Estimation).filter(Estimation.status == "FINAL").count()
    estimations_approved = session.query(Estimation).filter(Estimation.status == "APPROVED").count()

    avg_hours = session.query(sqlfunc.avg(Estimation.grand_total_hours)).scalar() or 0

    recent_estimations = (
        session.query(Estimation).order_by(Estimation.created_at.desc()).limit(5).all()
    )
    recent_requests = session.query(Request).order_by(Request.created_at.desc()).limit(5).all()

    return {
        "total_requests": total_requests,
        "requests_new": requests_new,
        "requests_in_progress": requests_in_progress,
        "requests_completed": requests_completed,
        "total_estimations": total_estimations,
        "estimations_draft": estimations_draft,
        "estimations_final": estimations_final,
        "estimations_approved": estimations_approved,
        "avg_grand_total_hours": round(float(avg_hours), 1),
        "recent_estimations": [
            {
                "id": e.id,
                "estimation_number": e.estimation_number,
                "project_name": e.project_name,
                "grand_total_hours": e.grand_total_hours,
                "feasibility_status": e.feasibility_status,
                "status": e.status,
                "created_at": str(e.created_at) if e.created_at else None,
            }
            for e in recent_estimations
        ],
        "recent_requests": [
            {
                "id": r.id,
                "request_number": r.request_number,
                "title": r.title,
                "priority": r.priority,
                "status": r.status,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in recent_requests
        ],
    }


# ── Calculation ──────────────────────────────────────────


def handle_calculate_estimation(session: Session, payload: dict) -> dict:
    """Run full estimation calculation from wizard inputs."""
    leader_ratio = float(_get_config(session, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config(session, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config(session, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config(session, "buffer_percentage", "10"))

    feature_ids = payload.get("features", [])
    new_feature_ids = payload.get("new_features", [])

    features = session.query(Feature).filter(Feature.id.in_(feature_ids)).all() if feature_ids else []
    templates = session.query(TaskTemplate).filter(
        (TaskTemplate.feature_id.in_(feature_ids)) | (TaskTemplate.feature_id.is_(None))
    ).all() if feature_ids else session.query(TaskTemplate).filter(TaskTemplate.feature_id.is_(None)).all()

    task_inputs: list[TaskInput] = []
    for tmpl in templates:
        feat = next((f for f in features if f.id == tmpl.feature_id), None)
        cw = feat.complexity_weight if feat else 1.0
        task_inputs.append(TaskInput(
            name=tmpl.name,
            task_type=tmpl.task_type,
            base_effort_hours=tmpl.base_effort_hours,
            scales_with_dut=tmpl.scales_with_dut,
            scales_with_profile=tmpl.scales_with_profile,
            complexity_weight=cw,
            is_new_feature_study=tmpl.feature_id in new_feature_ids if tmpl.feature_id else False,
            template_id=tmpl.id,
        ))

    pr_data = payload.get("pr_fixes", {})
    dut_count = len(payload.get("dut_ids", [])) or 1
    profile_count = len(payload.get("profile_ids", [])) or 1

    calc_input = EstimationInput(
        project_type=payload.get("project_type", "NEW"),
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        pr_fixes=PRFixInput(
            simple=pr_data.get("simple", 0),
            medium=pr_data.get("medium", 0),
            complex=pr_data.get("complex", 0),
        ),
        new_feature_count=len(new_feature_ids),
        team_size=payload.get("team_size", 1),
        has_leader=payload.get("has_leader", False),
        working_days=payload.get("working_days", 20),
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
    )

    result = calculate_estimation(calc_input)

    # Risk flags
    ref_ids = payload.get("reference_project_ids", [])
    matrix = payload.get("dut_profile_matrix", [])
    combos = len(matrix) if matrix else dut_count * profile_count

    delivery_str = payload.get("delivery_date")
    delivery_date = None
    if delivery_str:
        delivery_date = date.fromisoformat(delivery_str)

    risks = assess_risks(
        total_features=len(feature_ids),
        new_feature_count=len(new_feature_ids),
        reference_project_count=len(ref_ids),
        delivery_date=delivery_date,
        dut_profile_combinations=combos,
    )

    return {
        "tasks": [
            {
                "name": t.name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "dut_multiplier": t.dut_multiplier,
                "profile_multiplier": t.profile_multiplier,
                "complexity_weight": t.complexity_weight,
                "calculated_hours": t.calculated_hours,
                "is_new_feature_study": t.is_new_feature_study,
            }
            for t in result.tasks
        ],
        "total_tester_hours": result.total_tester_hours,
        "total_leader_hours": result.total_leader_hours,
        "pr_fix_hours": result.pr_fix_hours,
        "study_hours": result.study_hours,
        "buffer_hours": result.buffer_hours,
        "grand_total_hours": result.grand_total_hours,
        "grand_total_days": result.grand_total_days,
        "feasibility_status": result.feasibility_status,
        "capacity_hours": result.capacity_hours,
        "utilization_pct": result.utilization_pct,
        "risk_flags": [f.value for f in risks.flags],
        "risk_messages": risks.messages,
    }


# ── Report Generation ────────────────────────────────────


def _build_report_data(estimation: Estimation, session: Session):
    """Build the shared report data object from an estimation."""
    from ..reports.excel_report import ExcelReportData

    req = estimation.request
    ref_ids = json.loads(estimation.reference_project_ids) if estimation.reference_project_ids else []
    ref_projects = []
    if ref_ids:
        refs = session.query(HistoricalProject).filter(HistoricalProject.id.in_(ref_ids)).all()
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

    tasks = [
        {
            "task_name": t.task_name,
            "task_type": t.task_type,
            "base_hours": t.base_hours,
            "calculated_hours": t.calculated_hours,
            "is_new_feature_study": t.is_new_feature_study,
            "notes": t.notes or "",
        }
        for t in estimation.tasks
    ]

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
        grand_total_hours=estimation.grand_total_hours,
        grand_total_days=estimation.grand_total_days,
        feasibility_status=estimation.feasibility_status,
        tasks=tasks,
        reference_projects=ref_projects,
    )


def handle_generate_report(session: Session, payload: dict) -> dict:
    """Generate a report and return base64-encoded content."""
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")

    fmt = payload.get("format", "xlsx").lower()
    report_type = payload.get("report_type", "standard")

    if report_type == "executive_summary":
        from ..reports.executive_summary import ExecutiveSummaryData, generate_executive_summary
        data = ExecutiveSummaryData(
            project_name=est.project_name,
            estimation_number=est.estimation_number or "",
            project_type=est.project_type,
            created_by=est.created_by,
            created_at=str(est.created_at.date()) if est.created_at else "",
            grand_total_hours=est.grand_total_hours,
            grand_total_days=est.grand_total_days,
            feasibility_status=est.feasibility_status,
            total_tester_hours=est.total_tester_hours,
            total_leader_hours=est.total_leader_hours,
            dut_count=est.dut_count,
            profile_count=est.profile_count,
            dut_profile_combinations=est.dut_profile_combinations,
            tasks=[
                {"task_name": t.task_name, "task_type": t.task_type, "calculated_hours": t.calculated_hours}
                for t in est.tasks
            ],
        )
        content = generate_executive_summary(data)
        mime = "application/pdf"
        ext = "pdf"
    elif report_type == "comparison" and payload.get("compare_with_id"):
        est_b = session.get(Estimation, payload["compare_with_id"])
        if not est_b:
            raise ValueError(f"Comparison estimation {payload['compare_with_id']} not found")
        from ..reports.comparison_report import generate_comparison_excel
        from ..reports.templates import ComparisonReportData

        def _est_dict(e):
            return {
                "estimation_number": e.estimation_number,
                "project_name": e.project_name,
                "project_type": e.project_type,
                "grand_total_hours": e.grand_total_hours,
                "grand_total_days": e.grand_total_days,
                "total_tester_hours": e.total_tester_hours,
                "total_leader_hours": e.total_leader_hours,
                "feasibility_status": e.feasibility_status,
                "dut_count": e.dut_count,
                "profile_count": e.profile_count,
                "dut_profile_combinations": e.dut_profile_combinations,
                "pr_fix_count": e.pr_fix_count,
                "status": e.status,
                "tasks": [
                    {"task_name": t.task_name, "task_type": t.task_type, "calculated_hours": t.calculated_hours}
                    for t in e.tasks
                ],
            }

        data = ComparisonReportData(estimation_a=_est_dict(est), estimation_b=_est_dict(est_b))
        content = generate_comparison_excel(data)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        # Standard reports
        report_data = _build_report_data(est, session)
        if fmt == "xlsx":
            from ..reports.excel_report import generate_excel_report
            content = generate_excel_report(report_data)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        elif fmt == "docx":
            from ..reports.word_report import generate_word_report
            content = generate_word_report(report_data)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"
        elif fmt == "pdf":
            from ..reports.pdf_report import generate_pdf_report
            content = generate_pdf_report(report_data)
            mime = "application/pdf"
            ext = "pdf"
        else:
            raise ValueError(f"Unsupported format: {fmt}. Use xlsx, docx, or pdf.")

    filename = f"{est.estimation_number or f'EST-{est.id}'}.{ext}"
    encoded = base64.b64encode(content).decode("ascii")

    return {
        "filename": filename,
        "mime_type": mime,
        "content_base64": encoded,
        "size_bytes": len(content),
    }


def handle_generate_trend_report(session: Session, payload: dict) -> dict:
    """Generate trend analysis report from historical projects."""
    from ..reports.trend_report import generate_trend_excel
    from ..reports.templates import TrendReportData

    projects = session.query(HistoricalProject).all()
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
    encoded = base64.b64encode(content).decode("ascii")
    return {
        "filename": "trend_analysis.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content_base64": encoded,
        "size_bytes": len(content),
    }


# ── Bulk Import ─────────────────────────────────────────


def handle_preview_import(session: Session, payload: dict) -> dict:
    """Preview import data without persisting."""
    from ..imports.service import preview_import
    import base64 as b64

    content = b64.b64decode(payload["content_base64"])
    return preview_import(content, payload["entity_type"], payload.get("filename", "data.csv"))


def handle_import_data(session: Session, payload: dict, user: User | None = None) -> dict:
    """Import data from base64-encoded file content."""
    if not user or not AuthService.has_permission(user.role, "APPROVER"):
        raise ValueError("Approver access required")

    from ..imports.service import execute_import
    import base64 as b64

    content = b64.b64decode(payload["content_base64"])
    result = execute_import(
        content, payload["entity_type"],
        payload.get("filename", "data.csv"),
        session,
        payload.get("skip_duplicates", True),
    )
    AuthService(session).log_action(
        user.id, "IMPORT", payload["entity_type"],
        details={"imported": result["imported"], "skipped": result["skipped"]},
    )
    return result


# ── Integrations ─────────────────────────────────────────


def handle_get_integrations(session: Session, payload: dict) -> dict:
    configs = session.query(IntegrationConfig).all()
    return {
        "integrations": [
            {
                "id": c.id,
                "system_name": c.system_name,
                "base_url": c.base_url,
                "username": c.username,
                "additional_config_json": c.additional_config_json or "{}",
                "enabled": c.enabled,
                "last_sync_at": str(c.last_sync_at) if c.last_sync_at else None,
                "has_api_key": bool(c.api_key),
            }
            for c in configs
        ]
    }


def handle_update_integration(session: Session, payload: dict) -> dict:
    system_name = payload["system_name"].upper()
    cfg = session.query(IntegrationConfig).filter(
        IntegrationConfig.system_name == system_name
    ).first()
    if not cfg:
        cfg = IntegrationConfig(system_name=system_name)
        session.add(cfg)

    for key in ("base_url", "api_key", "username", "additional_config_json", "enabled"):
        if key in payload:
            setattr(cfg, key, payload[key])
    session.commit()
    session.refresh(cfg)
    return {"id": cfg.id, "system_name": cfg.system_name, "enabled": cfg.enabled}


def handle_test_integration(session: Session, payload: dict) -> dict:
    from ..integrations.service import test_integration
    result = test_integration(payload["system_name"].upper(), session)
    return {"success": result.success, "message": result.message, "details": result.details}


def handle_trigger_sync(session: Session, payload: dict) -> dict:
    from ..integrations.service import sync_import
    result = sync_import(payload["system_name"].upper(), session)
    return {
        "system": result.system,
        "direction": result.direction,
        "status": result.status.value,
        "items_processed": result.items_processed,
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "items_failed": result.items_failed,
        "errors": result.errors,
    }


# ── Outline Wiki ────────────────────────────────────────


def handle_outline_publish(session: Session, payload: dict) -> dict:
    """Publish estimation to Outline wiki."""
    est = session.get(Estimation, payload["id"])
    if not est:
        raise ValueError(f"Estimation {payload['id']} not found")

    from ..integrations.service import get_adapter
    adapter = get_adapter("OUTLINE", session)
    if not adapter:
        raise ValueError("Outline integration is not configured")

    est_data = {
        "estimation_number": est.estimation_number,
        "project_name": est.project_name,
        "project_type": est.project_type,
        "total_tester_hours": est.total_tester_hours,
        "total_leader_hours": est.total_leader_hours,
        "grand_total_hours": est.grand_total_hours,
        "grand_total_days": est.grand_total_days,
        "feasibility_status": est.feasibility_status,
        "status": est.status,
        "dut_count": est.dut_count,
        "profile_count": est.profile_count,
        "dut_profile_combinations": est.dut_profile_combinations,
        "pr_fix_count": est.pr_fix_count,
        "created_at": str(est.created_at) if est.created_at else "",
        "tasks": [
            {"task_name": t.task_name, "task_type": t.task_type, "calculated_hours": t.calculated_hours}
            for t in est.tasks
        ],
    }
    result = adapter.export_estimation(est_data)
    return {
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "errors": result.errors,
    }


def handle_outline_search(session: Session, payload: dict) -> dict:
    from ..integrations.service import get_adapter
    adapter = get_adapter("OUTLINE", session)
    if not adapter:
        raise ValueError("Outline integration is not configured")
    results = adapter.search_documents(
        payload.get("query", ""),
        payload.get("limit", 10),
    )
    return {"results": results}


# ── LDAP Sync ───────────────────────────────────────────


def handle_ldap_sync(session: Session, payload: dict, user: User | None = None) -> dict:
    if not user or not AuthService.has_permission(user.role, "ADMIN"):
        raise ValueError("Admin access required")
    from ..auth.ldap_provider import LDAPProvider
    provider = LDAPProvider(session)
    if not provider.is_configured:
        raise ValueError("LDAP is not configured")
    result = provider.sync_users()
    AuthService(session).log_action(user.id, "LDAP_SYNC", details=result)
    return result


# ── Command dispatch table ───────────────────────────────

# Commands that don't require authentication
PUBLIC_COMMANDS: dict[str, callable] = {
    "login": handle_login,
    "refresh_token": handle_refresh_token,
    "logout": handle_logout,
    "validate_session": handle_validate_session,
}

# Commands that accept user context (token validated, user passed as kwarg)
AUTH_AWARE_COMMANDS: dict[str, callable] = {
    "get_current_user": handle_get_current_user,
    "change_password": handle_change_password,
    # Users
    "get_users": handle_get_users,
    "create_user": handle_create_user,
    "update_user": handle_update_user,
    "delete_user": handle_delete_user,
    # Audit log
    "get_audit_log": handle_get_audit_log,
    # Assignment
    "assign_estimation": handle_assign_estimation,
    "assign_request": handle_assign_request,
    # Import
    "preview_import": handle_preview_import,
    "import_data": handle_import_data,
    # LDAP
    "ldap_sync": handle_ldap_sync,
}

# Commands that work with or without auth (backward compatible)
COMMANDS: dict[str, callable] = {
    # Features
    "get_features": handle_get_features,
    "create_feature": handle_create_feature,
    "update_feature": handle_update_feature,
    "delete_feature": handle_delete_feature,
    # DUT types
    "get_dut_types": handle_get_dut_types,
    "create_dut_type": handle_create_dut_type,
    "update_dut_type": handle_update_dut_type,
    "delete_dut_type": handle_delete_dut_type,
    # Profiles
    "get_profiles": handle_get_profiles,
    "create_profile": handle_create_profile,
    "update_profile": handle_update_profile,
    "delete_profile": handle_delete_profile,
    # Team members
    "get_team_members": handle_get_team_members,
    "create_team_member": handle_create_team_member,
    "update_team_member": handle_update_team_member,
    "delete_team_member": handle_delete_team_member,
    # Historical projects
    "get_historical_projects": handle_get_historical_projects,
    "create_historical_project": handle_create_historical_project,
    # Requests
    "get_requests": handle_get_requests,
    "create_request": handle_create_request,
    "update_request": handle_update_request,
    # Estimations
    "get_estimations": handle_get_estimations,
    "get_estimation": handle_get_estimation,
    "save_estimation": handle_save_estimation,
    "update_estimation_status": handle_update_estimation_status,
    "export_estimation": handle_export_estimation,
    "calculate_estimation": handle_calculate_estimation,
    # Dashboard
    "get_dashboard_stats": handle_get_dashboard_stats,
    # Reports
    "generate_report": handle_generate_report,
    "generate_trend_report": handle_generate_trend_report,
    # Configuration
    "get_configuration": handle_get_configuration,
    "set_configuration": handle_set_configuration,
    # Integrations
    "get_integrations": handle_get_integrations,
    "update_integration": handle_update_integration,
    "test_integration": handle_test_integration,
    "trigger_sync": handle_trigger_sync,
    # Outline
    "outline_publish": handle_outline_publish,
    "outline_search": handle_outline_search,
}


def process_command(input_data: dict, db_path: str | None = None) -> dict:
    """Process a single IPC command and return the response."""
    command = input_data.get("command")
    payload = input_data.get("payload", {})
    token = input_data.get("token")

    if not command:
        return {"status": "error", "message": "Missing 'command' field"}

    # Check public commands first (no auth needed)
    if command in PUBLIC_COMMANDS:
        session = _get_session(db_path)
        try:
            result = PUBLIC_COMMANDS[command](session, payload)
            return {"status": "ok", "result": result}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
        finally:
            session.close()

    # Check auth-aware commands (require valid user)
    if command in AUTH_AWARE_COMMANDS:
        session = _get_session(db_path)
        try:
            user = _validate_token(session, token)
            result = AUTH_AWARE_COMMANDS[command](session, payload, user=user)
            return {"status": "ok", "result": result}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
        finally:
            session.close()

    # Regular commands (work with or without auth for backward compat)
    handler = COMMANDS.get(command)
    if not handler:
        return {"status": "error", "message": f"Unknown command: {command}"}

    session = _get_session(db_path)
    try:
        result = handler(session, payload)
        return {"status": "ok", "result": result}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
    finally:
        session.close()


def main(db_path: str | None = None) -> None:
    """Main IPC loop: read JSON from stdin, process, write JSON to stdout."""
    init_database(db_path)

    # Signal readiness
    print(json.dumps({"status": "ready"}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            input_data = json.loads(line)
        except json.JSONDecodeError as e:
            response = {"status": "error", "message": f"Invalid JSON: {e}"}
            print(json.dumps(response), flush=True)
            continue

        response = process_command(input_data, db_path)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    main(db)
