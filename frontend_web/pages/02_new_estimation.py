"""New Estimation — 7-step wizard.

Allows users to create a full test effort estimation by walking through:
  Step 1: Request & Project Type
  Step 2: Feature Selection
  Step 3: Reference Projects
  Step 4: DUT & Profile Matrix
  Step 5: PR Fixes
  Step 6: Delivery Date & Team
  Step 7: Review & Generate
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Backend path setup ────────────────────────────────────────────────────────
backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import streamlit as st

from src.database.migrations import get_engine
from src.database.models import (
    DutType,
    Estimation,
    EstimationTask,
    Feature,
    HistoricalProject,
    Request,
    TaskTemplate,
    TeamMember,
    TestProfile,
)
from src.engine.calculator import (
    EstimationInput,
    PRFixInput,
    TaskInput,
    calculate_estimation,
)
from src.engine.calibration import HistoricalDataPoint, calibrate
from src.engine.feasibility import assess_risks
from src.reports.excel_report import ExcelReportData, generate_excel_report
from src.reports.word_report import generate_word_report
from sqlalchemy.orm import Session

# ── Session-state initialisation ──────────────────────────────────────────────
WIZARD_DEFAULTS: dict = {
    # Step 1
    "s1_mode": "link",           # "link" | "create"
    "s1_request_id": None,
    "s1_project_name": "",
    "s1_project_type": "NEW",
    "s1_requester_name": "",
    "s1_requester_email": "",
    "s1_business_unit": "",
    "s1_priority": "MEDIUM",
    "s1_description": "",
    # Step 2
    "s2_selected_feature_ids": [],
    "s2_new_feature_ids": [],      # subset flagged as new (no existing tests)
    # Step 3
    "s3_reference_project_ids": [],
    # Step 4
    "s4_selected_dut_ids": [],
    "s4_selected_profile_ids": [],
    "s4_combinations": [],         # list of [dut_id, profile_id]
    # Step 5
    "s5_pr_simple": 0,
    "s5_pr_medium": 0,
    "s5_pr_complex": 0,
    # Step 6
    "s6_delivery_date": date.today() + timedelta(days=30),
    "s6_team_size": 2,
    "s6_has_leader": False,
    "s6_working_days": 20,
    # Result cache
    "calc_result": None,
    "risk_result": None,
    "calibration_result": None,
    "saved_estimation_id": None,
}

for key, default in WIZARD_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Edit-mode: pre-fill wizard from an existing REVISED estimation ────────────
def _load_edit_estimation() -> None:
    """If redirected from detail page with edit_estimation_id, pre-fill the wizard."""
    edit_id = st.session_state.pop("edit_estimation_id", None)
    if edit_id is None:
        return

    engine = get_engine()
    with Session(engine) as session:
        est = session.get(Estimation, edit_id)
        if not est or est.status != "REVISED":
            return

        # Parse wizard_inputs_json (use getattr for DBs not yet migrated to v3)
        raw = getattr(est, "wizard_inputs_json", None) or "{}"
        try:
            inputs = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            inputs = {}

        st.session_state["s1_project_name"] = est.project_name
        st.session_state["s1_project_type"] = est.project_type
        st.session_state["s1_request_id"] = est.request_id
        feature_ids = inputs.get("feature_ids", [])
        new_feature_ids = inputs.get("new_feature_ids", [])
        reference_project_ids = inputs.get("reference_project_ids", [])
        dut_ids = inputs.get("dut_ids", [])
        profile_ids = inputs.get("profile_ids", [])
        combinations = inputs.get("dut_profile_matrix", [])
        pr = inputs.get("pr_fixes", {})
        pr_simple = pr.get("simple", 0)
        pr_medium = pr.get("medium", 0)
        pr_complex = pr.get("complex", 0)
        team_size = inputs.get("team_size", 2)
        has_leader = inputs.get("has_leader", False)
        working_days = inputs.get("working_days", 20)

        # ── Set list-level state keys ──────────────────────────────────────────
        st.session_state["s2_selected_feature_ids"] = feature_ids
        st.session_state["s2_new_feature_ids"] = new_feature_ids
        st.session_state["s3_reference_project_ids"] = reference_project_ids
        st.session_state["s4_selected_dut_ids"] = dut_ids
        st.session_state["s4_selected_profile_ids"] = profile_ids
        st.session_state["s4_combinations"] = combinations
        st.session_state["s5_pr_simple"] = pr_simple
        st.session_state["s5_pr_medium"] = pr_medium
        st.session_state["s5_pr_complex"] = pr_complex
        st.session_state["s6_team_size"] = team_size
        st.session_state["s6_has_leader"] = has_leader
        st.session_state["s6_working_days"] = working_days
        if est.expected_delivery:
            st.session_state["s6_delivery_date"] = est.expected_delivery

        # ── Step 1: set mode based on whether there is a linked request ────────
        st.session_state["s1_mode"] = "link" if est.request_id else "create"

        # ── Clear stale individual widget keys from any previous wizard run ────
        stale_prefixes = ("s2_feat_", "s2_new_", "s3_ref_", "s4_dut_", "s4_prof_", "s4_combo_")
        stale_keys = [k for k in list(st.session_state.keys()) if k.startswith(stale_prefixes)]
        for k in stale_keys:
            del st.session_state[k]

        # ── Step 2: sync feature checkbox widget keys ──────────────────────────
        for fid in feature_ids:
            st.session_state[f"s2_feat_{fid}"] = True
        for fid in new_feature_ids:
            st.session_state[f"s2_new_{fid}"] = True

        # ── Step 3: sync reference project checkbox widget keys ────────────────
        for rid in reference_project_ids:
            st.session_state[f"s3_ref_{rid}"] = True

        # ── Step 4: sync DUT, profile, and combination checkbox widget keys ────
        for did in dut_ids:
            st.session_state[f"s4_dut_{did}"] = True
        for pid in profile_ids:
            st.session_state[f"s4_prof_{pid}"] = True
        for combo in combinations:
            if isinstance(combo, (list, tuple)) and len(combo) == 2:
                st.session_state[f"s4_combo_{combo[0]}_{combo[1]}"] = True

        # ── Step 5: sync number input widget keys ──────────────────────────────
        st.session_state["s5_simple_input"] = pr_simple
        st.session_state["s5_medium_input"] = pr_medium
        st.session_state["s5_complex_input"] = pr_complex

        # ── Step 6: sync team / schedule widget keys ───────────────────────────
        st.session_state["s6_team_size_input"] = team_size
        st.session_state["s6_working_days_input"] = working_days
        st.session_state["s6_has_leader_toggle"] = has_leader
        if est.expected_delivery:
            st.session_state["s6_delivery_date_input"] = est.expected_delivery

        # Store edit context so save can revise instead of create
        st.session_state["_edit_estimation_id"] = edit_id
        st.session_state["_edit_estimation_version"] = getattr(est, "version", 1) or 1

        st.session_state["calc_result"] = None
        st.session_state["saved_estimation_id"] = None


_load_edit_estimation()


# ── DB helpers ────────────────────────────────────────────────────────────────
@st.cache_resource
def _engine():
    return get_engine()


def _session() -> Session:
    return Session(_engine())


@st.cache_data(ttl=60)
def load_features() -> list[dict]:
    with _session() as s:
        rows = s.query(Feature).order_by(Feature.category, Feature.name).all()
        return [
            {
                "id": f.id,
                "name": f.name,
                "category": f.category or "Uncategorised",
                "complexity_weight": f.complexity_weight,
                "has_existing_tests": f.has_existing_tests,
                "description": f.description or "",
            }
            for f in rows
        ]


@st.cache_data(ttl=60)
def load_task_templates() -> list[dict]:
    with _session() as s:
        rows = s.query(TaskTemplate).all()
        return [
            {
                "id": t.id,
                "feature_id": t.feature_id,
                "name": t.name,
                "task_type": t.task_type,
                "base_effort_hours": t.base_effort_hours,
                "scales_with_dut": t.scales_with_dut,
                "scales_with_profile": t.scales_with_profile,
            }
            for t in rows
        ]


@st.cache_data(ttl=60)
def load_dut_types() -> list[dict]:
    with _session() as s:
        rows = s.query(DutType).order_by(DutType.category, DutType.name).all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "category": d.category or "General",
                "complexity_multiplier": d.complexity_multiplier,
            }
            for d in rows
        ]


@st.cache_data(ttl=60)
def load_test_profiles() -> list[dict]:
    with _session() as s:
        rows = s.query(TestProfile).order_by(TestProfile.name).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "effort_multiplier": p.effort_multiplier,
            }
            for p in rows
        ]


@st.cache_data(ttl=60)
def load_historical_projects() -> list[dict]:
    with _session() as s:
        rows = (
            s.query(HistoricalProject)
            .order_by(HistoricalProject.completion_date.desc())
            .all()
        )
        return [
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
                "completion_date": p.completion_date,
                "notes": p.notes or "",
            }
            for p in rows
        ]


@st.cache_data(ttl=60)
def load_requests() -> list[dict]:
    with _session() as s:
        rows = (
            s.query(Request)
            .filter(Request.status.in_(["NEW", "IN_PROGRESS"]))
            .order_by(Request.received_date.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "request_number": r.request_number,
                "title": r.title,
                "requester_name": r.requester_name,
                "requester_email": r.requester_email or "",
                "business_unit": r.business_unit or "",
                "priority": r.priority,
                "status": r.status,
                "description": r.description or "",
                "requested_delivery_date": r.requested_delivery_date,
            }
            for r in rows
        ]


# ── Calculation helpers ───────────────────────────────────────────────────────

def _build_task_inputs(
    selected_feature_ids: list[int],
    new_feature_ids: list[int],
    project_type: str,
) -> list[TaskInput]:
    """Build TaskInput list from selected features and their templates."""
    features = {f["id"]: f for f in load_features()}
    templates = load_task_templates()

    template_by_feature: dict[int, list[dict]] = {}
    for t in templates:
        if t["feature_id"] is not None:
            template_by_feature.setdefault(t["feature_id"], []).append(t)

    task_inputs: list[TaskInput] = []
    for fid in selected_feature_ids:
        feat = features.get(fid)
        if feat is None:
            continue
        is_new = fid in new_feature_ids
        feat_templates = template_by_feature.get(fid, [])

        if feat_templates:
            for tmpl in feat_templates:
                task_inputs.append(
                    TaskInput(
                        name=tmpl["name"],
                        task_type=tmpl["task_type"],
                        base_effort_hours=tmpl["base_effort_hours"],
                        scales_with_dut=tmpl["scales_with_dut"],
                        scales_with_profile=tmpl["scales_with_profile"],
                        complexity_weight=feat["complexity_weight"],
                        is_new_feature_study=is_new,
                        template_id=tmpl["id"],
                    )
                )
        else:
            # Fallback: synthesise a single EXECUTION task from the feature itself
            task_inputs.append(
                TaskInput(
                    name=f"{feat['name']} — Execution",
                    task_type="EXECUTION",
                    base_effort_hours=4.0 * feat["complexity_weight"],
                    scales_with_dut=True,
                    scales_with_profile=True,
                    complexity_weight=feat["complexity_weight"],
                    is_new_feature_study=is_new,
                )
            )

    return task_inputs


def _run_calculation() -> None:
    """Run the estimation engine and store results in session state."""
    dut_ids = st.session_state["s4_selected_dut_ids"]
    profile_ids = st.session_state["s4_selected_profile_ids"]
    combinations = st.session_state["s4_combinations"]
    feature_ids = st.session_state["s2_selected_feature_ids"]
    new_feature_ids = st.session_state["s2_new_feature_ids"]
    project_type = st.session_state["s1_project_type"]

    dut_count = len(dut_ids) if dut_ids else 1
    profile_count = len(profile_ids) if profile_ids else 1
    dut_profile_combinations = len(combinations) if combinations else dut_count * profile_count

    task_inputs = _build_task_inputs(feature_ids, new_feature_ids, project_type)

    pr_input = PRFixInput(
        simple=st.session_state["s5_pr_simple"],
        medium=st.session_state["s5_pr_medium"],
        complex=st.session_state["s5_pr_complex"],
    )

    estimation_input = EstimationInput(
        project_type=project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        pr_fixes=pr_input,
        new_feature_count=len(new_feature_ids),
        team_size=st.session_state["s6_team_size"],
        has_leader=st.session_state["s6_has_leader"],
        working_days=st.session_state["s6_working_days"],
    )

    result = calculate_estimation(estimation_input)
    st.session_state["calc_result"] = result

    # Risk assessment
    ref_projects = [
        p for p in load_historical_projects()
        if p["id"] in st.session_state["s3_reference_project_ids"]
    ]
    calib_data = [
        HistoricalDataPoint(
            project_name=p["project_name"],
            estimated_hours=p["estimated_hours"] or 0.0,
            actual_hours=p["actual_hours"] or 0.0,
            feature_ids=json.loads(p["features_json"]),
        )
        for p in ref_projects
        if (p["estimated_hours"] or 0) > 0
    ]
    calibration = calibrate(calib_data, feature_ids)
    st.session_state["calibration_result"] = calibration

    risk = assess_risks(
        total_features=len(feature_ids),
        new_feature_count=len(new_feature_ids),
        reference_project_count=len(ref_projects),
        delivery_date=st.session_state["s6_delivery_date"],
        dut_profile_combinations=dut_profile_combinations,
        historical_accuracy_ratio=calibration.accuracy_ratio if calib_data else None,
    )
    st.session_state["risk_result"] = risk


def _build_wizard_inputs_json() -> str:
    """Serialize current wizard inputs to JSON for storage."""
    return json.dumps({
        "feature_ids": st.session_state["s2_selected_feature_ids"],
        "new_feature_ids": st.session_state["s2_new_feature_ids"],
        "reference_project_ids": st.session_state["s3_reference_project_ids"],
        "dut_ids": st.session_state["s4_selected_dut_ids"],
        "profile_ids": st.session_state["s4_selected_profile_ids"],
        "dut_profile_matrix": st.session_state["s4_combinations"],
        "pr_fixes": {
            "simple": st.session_state["s5_pr_simple"],
            "medium": st.session_state["s5_pr_medium"],
            "complex": st.session_state["s5_pr_complex"],
        },
        "team_size": st.session_state["s6_team_size"],
        "has_leader": st.session_state["s6_has_leader"],
        "working_days": st.session_state["s6_working_days"],
    })


def _save_to_database() -> int:
    """Persist the estimation and its tasks to the database. Returns estimation id."""
    result = st.session_state["calc_result"]
    if result is None:
        raise ValueError("No calculation result to save.")

    project_name = st.session_state["s1_project_name"] or "Untitled Estimation"
    project_type = st.session_state["s1_project_type"]
    request_id = st.session_state["s1_request_id"]
    ref_ids = st.session_state["s3_reference_project_ids"]
    dut_ids = st.session_state["s4_selected_dut_ids"]
    profile_ids = st.session_state["s4_selected_profile_ids"]
    combinations = st.session_state["s4_combinations"]
    dut_count = len(dut_ids) if dut_ids else 1
    profile_count = len(profile_ids) if profile_ids else 1
    dut_profile_combinations = len(combinations) if combinations else dut_count * profile_count
    pr_total = (
        st.session_state["s5_pr_simple"]
        + st.session_state["s5_pr_medium"]
        + st.session_state["s5_pr_complex"]
    )
    wizard_inputs = _build_wizard_inputs_json()

    # ── Revision mode: update existing estimation ──
    edit_id = st.session_state.get("_edit_estimation_id")
    if edit_id:
        return _revise_estimation(edit_id, result, project_name, project_type,
                                  ref_ids, dut_count, profile_count,
                                  dut_profile_combinations, pr_total, wizard_inputs)

    # ── Normal mode: create new estimation ──
    with _session() as session:
        # Generate estimation number
        count = session.query(Estimation).count()
        est_number = f"EST-{date.today().year}-{count + 1:04d}"

        estimation = Estimation(
            request_id=request_id,
            estimation_number=est_number,
            project_name=project_name,
            project_type=project_type,
            reference_project_ids=json.dumps(ref_ids),
            dut_count=dut_count,
            profile_count=profile_count,
            dut_profile_combinations=dut_profile_combinations,
            pr_fix_count=pr_total,
            expected_delivery=st.session_state["s6_delivery_date"],
            total_tester_hours=round(result.total_tester_hours, 2),
            total_leader_hours=round(result.total_leader_hours, 2),
            grand_total_hours=round(result.grand_total_hours, 2),
            grand_total_days=round(result.grand_total_days, 1),
            feasibility_status=result.feasibility_status,
            status="DRAFT",
            version=1,
            wizard_inputs_json=wizard_inputs,
        )
        session.add(estimation)
        session.flush()

        # Auto-update linked request status
        if request_id:
            req = session.get(Request, request_id)
            if req and req.status == "NEW":
                req.status = "IN_ESTIMATION"

        _create_estimation_tasks(session, estimation.id, result)

        session.commit()
        saved_id = estimation.id
        st.session_state["saved_estimation_id"] = saved_id
        return saved_id


def _revise_estimation(edit_id, result, project_name, project_type,
                       ref_ids, dut_count, profile_count,
                       dut_profile_combinations, pr_total, wizard_inputs) -> int:
    """Update an existing REVISED estimation in-place, bumping the version."""
    with _session() as session:
        estimation = session.get(Estimation, edit_id)
        if not estimation:
            raise ValueError(f"Estimation {edit_id} not found.")

        old_version = st.session_state.get("_edit_estimation_version", 1)

        estimation.project_name = project_name
        estimation.project_type = project_type
        estimation.reference_project_ids = json.dumps(ref_ids)
        estimation.dut_count = dut_count
        estimation.profile_count = profile_count
        estimation.dut_profile_combinations = dut_profile_combinations
        estimation.pr_fix_count = pr_total
        estimation.expected_delivery = st.session_state["s6_delivery_date"]
        estimation.total_tester_hours = round(result.total_tester_hours, 2)
        estimation.total_leader_hours = round(result.total_leader_hours, 2)
        estimation.grand_total_hours = round(result.grand_total_hours, 2)
        estimation.grand_total_days = round(result.grand_total_days, 1)
        estimation.feasibility_status = result.feasibility_status
        estimation.status = "DRAFT"
        estimation.version = old_version + 1
        estimation.wizard_inputs_json = wizard_inputs

        # Clear approval fields
        estimation.approved_by = None
        estimation.approved_at = None

        # Delete old tasks and create new ones
        session.query(EstimationTask).filter(
            EstimationTask.estimation_id == edit_id
        ).delete()

        _create_estimation_tasks(session, edit_id, result)

        session.commit()

        # Clear edit mode
        st.session_state.pop("_edit_estimation_id", None)
        st.session_state.pop("_edit_estimation_version", None)
        st.session_state["saved_estimation_id"] = edit_id
        return edit_id


def _create_estimation_tasks(session, estimation_id: int, result) -> None:
    """Create EstimationTask rows from a calculation result."""
    for task_result in result.tasks:
        session.add(
            EstimationTask(
                estimation_id=estimation_id,
                task_template_id=task_result.template_id,
                task_name=task_result.name,
                task_type=task_result.task_type,
                base_hours=round(task_result.base_hours, 2),
                calculated_hours=round(task_result.calculated_hours, 2),
                assigned_testers=st.session_state["s6_team_size"],
                has_leader_support=st.session_state["s6_has_leader"],
                leader_hours=round(result.total_leader_hours / len(result.tasks), 2)
                if result.tasks else 0,
                is_new_feature_study=task_result.is_new_feature_study,
            )
        )


def _build_report_data() -> ExcelReportData:
    """Assemble ExcelReportData from session state for report generation."""
    result = st.session_state["calc_result"]
    risk = st.session_state["risk_result"]

    all_duts = {d["id"]: d for d in load_dut_types()}
    all_profiles = {p["id"]: p for p in load_test_profiles()}
    all_ref = {p["id"]: p for p in load_historical_projects()}

    selected_duts = [all_duts[i] for i in st.session_state["s4_selected_dut_ids"] if i in all_duts]
    selected_profiles = [all_profiles[i] for i in st.session_state["s4_selected_profile_ids"] if i in all_profiles]
    ref_projects = [all_ref[i] for i in st.session_state["s3_reference_project_ids"] if i in all_ref]
    combinations = st.session_state["s4_combinations"]

    tasks_dicts = [
        {
            "task_name": t.name,
            "task_type": t.task_type,
            "base_hours": t.base_hours,
            "dut_multiplier": t.dut_multiplier,
            "profile_multiplier": t.profile_multiplier,
            "complexity_weight": t.complexity_weight,
            "calculated_hours": t.calculated_hours,
            "is_new_feature_study": t.is_new_feature_study,
        }
        for t in result.tasks
    ] if result else []

    request_number = ""
    requester_name = ""
    business_unit = ""
    priority = ""
    if st.session_state["s1_request_id"]:
        for r in load_requests():
            if r["id"] == st.session_state["s1_request_id"]:
                request_number = r["request_number"]
                requester_name = r["requester_name"]
                business_unit = r["business_unit"]
                priority = r["priority"]
                break
    else:
        requester_name = st.session_state.get("s1_requester_name", "")
        business_unit = st.session_state.get("s1_business_unit", "")
        priority = st.session_state.get("s1_priority", "MEDIUM")

    est_id = st.session_state.get("saved_estimation_id")
    estimation_number = f"EST-PREVIEW" if not est_id else f"EST-{date.today().year}-{est_id:04d}"

    return ExcelReportData(
        project_name=st.session_state["s1_project_name"] or "Untitled",
        estimation_number=estimation_number,
        project_type=st.session_state["s1_project_type"],
        created_at=str(date.today()),
        request_number=request_number,
        requester_name=requester_name,
        business_unit=business_unit,
        priority=priority,
        dut_count=len(selected_duts) if selected_duts else 1,
        profile_count=len(selected_profiles) if selected_profiles else 1,
        dut_profile_combinations=len(combinations) if combinations else (len(selected_duts) or 1) * (len(selected_profiles) or 1),
        pr_fix_count=(
            st.session_state["s5_pr_simple"]
            + st.session_state["s5_pr_medium"]
            + st.session_state["s5_pr_complex"]
        ),
        expected_delivery=str(st.session_state["s6_delivery_date"]),
        total_tester_hours=result.total_tester_hours if result else 0,
        total_leader_hours=result.total_leader_hours if result else 0,
        pr_fix_hours=result.pr_fix_hours if result else 0,
        study_hours=result.study_hours if result else 0,
        buffer_hours=result.buffer_hours if result else 0,
        grand_total_hours=result.grand_total_hours if result else 0,
        grand_total_days=result.grand_total_days if result else 0,
        feasibility_status=result.feasibility_status if result else "FEASIBLE",
        capacity_hours=result.capacity_hours if result else 0,
        utilization_pct=result.utilization_pct if result else 0,
        tasks=tasks_dicts,
        dut_types=selected_duts,
        profiles=selected_profiles,
        dut_profile_matrix=combinations,
        team_size=st.session_state["s6_team_size"],
        has_leader=st.session_state["s6_has_leader"],
        pr_simple=st.session_state["s5_pr_simple"],
        pr_medium=st.session_state["s5_pr_medium"],
        pr_complex=st.session_state["s5_pr_complex"],
        reference_projects=ref_projects,
        risk_flags=[f.value for f in risk.flags] if risk else [],
        risk_messages=risk.messages if risk else [],
    )


# ── UI helpers ────────────────────────────────────────────────────────────────

def _feasibility_badge(status: str) -> str:
    colours = {
        "FEASIBLE": "green",
        "AT_RISK": "orange",
        "NOT_FEASIBLE": "red",
    }
    labels = {
        "FEASIBLE": "FEASIBLE",
        "AT_RISK": "AT RISK",
        "NOT_FEASIBLE": "NOT FEASIBLE",
    }
    colour = colours.get(status, "grey")
    label = labels.get(status, status)
    return f":{colour}[**{label}**]"


def _progress_bar(current_step: int, total: int = 7) -> None:
    pct = current_step / total
    cols = st.columns(total)
    for i, col in enumerate(cols):
        step_num = i + 1
        if step_num < current_step:
            col.markdown(f"<div style='text-align:center;color:#4CAF50;font-size:12px'>Step {step_num}<br>Done</div>", unsafe_allow_html=True)
        elif step_num == current_step:
            col.markdown(f"<div style='text-align:center;color:#1E88E5;font-weight:bold;font-size:12px'>Step {step_num}<br>Active</div>", unsafe_allow_html=True)
        else:
            col.markdown(f"<div style='text-align:center;color:#9E9E9E;font-size:12px'>Step {step_num}<br>Pending</div>", unsafe_allow_html=True)
    st.progress(pct)


# ── Step renderers ────────────────────────────────────────────────────────────

def render_step1() -> None:
    st.subheader("Step 1 — Request & Project Type")
    st.caption("Link this estimation to an existing service request or create one inline. Then choose the project type.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown("**Request**")
        mode = st.radio(
            "Request mode",
            options=["Link existing request", "Create inline (no request)"],
            index=0 if st.session_state["s1_mode"] == "link" else 1,
            key="s1_mode_radio",
            label_visibility="collapsed",
        )
        st.session_state["s1_mode"] = "link" if mode == "Link existing request" else "create"

        if st.session_state["s1_mode"] == "link":
            requests = load_requests()
            if not requests:
                st.warning("No open requests found. Use 'Create inline' or add requests via the Dashboard.")
            else:
                options = {r["id"]: f"{r['request_number']} — {r['title']}" for r in requests}
                selected_id = st.selectbox(
                    "Select request",
                    options=list(options.keys()),
                    format_func=lambda x: options[x],
                    index=0,
                    key="s1_request_selector",
                )
                st.session_state["s1_request_id"] = selected_id
                # Auto-populate from request
                selected_req = next((r for r in requests if r["id"] == selected_id), None)
                if selected_req:
                    if not st.session_state["s1_project_name"]:
                        st.session_state["s1_project_name"] = selected_req["title"]
                    with st.expander("Request details", expanded=False):
                        st.write(f"**Requester:** {selected_req['requester_name']}")
                        st.write(f"**Business unit:** {selected_req['business_unit'] or '-'}")
                        st.write(f"**Priority:** {selected_req['priority']}")
                        if selected_req["description"]:
                            st.write(f"**Description:** {selected_req['description']}")
        else:
            st.session_state["s1_request_id"] = None
            st.session_state["s1_requester_name"] = st.text_input(
                "Requester name",
                value=st.session_state["s1_requester_name"],
                key="s1_requester_name_input",
            )
            st.session_state["s1_requester_email"] = st.text_input(
                "Requester email (optional)",
                value=st.session_state["s1_requester_email"],
                key="s1_requester_email_input",
            )
            st.session_state["s1_business_unit"] = st.text_input(
                "Business unit (optional)",
                value=st.session_state["s1_business_unit"],
                key="s1_bu_input",
            )
            st.session_state["s1_priority"] = st.selectbox(
                "Priority",
                options=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                index=["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(
                    st.session_state["s1_priority"]
                ),
                key="s1_priority_select",
            )

    with col_b:
        st.markdown("**Project details**")
        st.session_state["s1_project_name"] = st.text_input(
            "Project / estimation name",
            value=st.session_state["s1_project_name"],
            placeholder="e.g. Release 3.2 — Camera Feature Pack",
            key="s1_project_name_input",
        )

        project_type = st.radio(
            "Project type",
            options=["NEW", "EVOLUTION", "SUPPORT"],
            index=["NEW", "EVOLUTION", "SUPPORT"].index(st.session_state["s1_project_type"]),
            key="s1_project_type_radio",
            help=(
                "**NEW** — Greenfield project; all features flagged for study.\n\n"
                "**EVOLUTION** — Extends an existing product; reference features pre-selected.\n\n"
                "**SUPPORT** — Regression/maintenance scope only."
            ),
        )
        st.session_state["s1_project_type"] = project_type

        type_descriptions = {
            "NEW": "All selected features will be flagged as requiring study effort (no existing tests assumed).",
            "EVOLUTION": "Reference project features will be pre-selected. You can add new ones.",
            "SUPPORT": "Focus on regression scope. New-feature study effort will be minimal.",
        }
        st.info(type_descriptions[project_type])

        st.session_state["s1_description"] = st.text_area(
            "Notes / description (optional)",
            value=st.session_state["s1_description"],
            key="s1_desc_input",
            height=80,
        )

    # Validation
    if not st.session_state["s1_project_name"].strip():
        st.error("A project name is required before proceeding.")
        return False
    if st.session_state["s1_mode"] == "link" and not st.session_state["s1_request_id"]:
        st.error("Select a request or switch to inline mode.")
        return False
    return True


def render_step2() -> None:
    st.subheader("Step 2 — Feature Selection")
    project_type = st.session_state["s1_project_type"]
    st.caption(
        f"Project type: **{project_type}**. "
        + {
            "NEW": "All selected features are treated as new (study effort added). Toggle off the 'New' flag for features that already have tests.",
            "EVOLUTION": "Features with existing tests are pre-selected. Select additional new features as needed.",
            "SUPPORT": "Only features with existing tests are relevant for a regression run.",
        }[project_type]
    )

    features = load_features()
    if not features:
        st.warning("No features found in the catalog. Add features via the Feature Catalog page.")
        return True  # allow proceeding without features

    # Group by category
    categories = sorted(set(f["category"] for f in features))

    # For EVOLUTION, pre-select features that have existing tests on first visit
    if project_type == "EVOLUTION" and not st.session_state["s2_selected_feature_ids"]:
        st.session_state["s2_selected_feature_ids"] = [
            f["id"] for f in features if f["has_existing_tests"]
        ]

    selected_ids: list[int] = list(st.session_state["s2_selected_feature_ids"])
    new_ids: list[int] = list(st.session_state["s2_new_feature_ids"])

    # For NEW projects, auto-flag all as new
    if project_type == "NEW":
        new_ids = list(selected_ids)

    search = st.text_input(
        "Search features",
        placeholder="Filter by name or category...",
        key="s2_search",
    )
    filter_term = search.lower().strip()

    # -- "Select all" across every category -----------------------------------
    all_visible_ids = [
        f["id"] for f in features
        if not filter_term or filter_term in f["name"].lower() or filter_term in f["category"].lower()
    ]
    all_selected = len(all_visible_ids) > 0 and all(fid in selected_ids for fid in all_visible_ids)

    def _on_select_all():
        toggled = st.session_state["s2_select_all"]
        sel = list(st.session_state["s2_selected_feature_ids"])
        for fid in all_visible_ids:
            if toggled and fid not in sel:
                sel.append(fid)
            elif not toggled and fid in sel:
                sel.remove(fid)
        st.session_state["s2_selected_feature_ids"] = sel
        # Sync individual checkbox widget states
        for fid in all_visible_ids:
            st.session_state[f"s2_feat_{fid}"] = toggled

    st.checkbox(
        f"Select all ({len(all_visible_ids)} features)",
        value=all_selected,
        key="s2_select_all",
        on_change=_on_select_all,
    )

    changed = False
    for cat in categories:
        cat_features = [
            f for f in features
            if f["category"] == cat and (
                not filter_term or filter_term in f["name"].lower() or filter_term in cat.lower()
            )
        ]
        if not cat_features:
            continue

        with st.expander(f"{cat} ({len([f for f in cat_features if f['id'] in selected_ids])} / {len(cat_features)} selected)", expanded=True):
            # "Select all in category" shortcut
            cat_all_selected = all(f["id"] in selected_ids for f in cat_features)

            def _on_cat_toggle(cat_name=cat, feats=cat_features):
                toggled = st.session_state[f"s2_cat_all_{cat_name}"]
                sel = list(st.session_state["s2_selected_feature_ids"])
                for f in feats:
                    if toggled and f["id"] not in sel:
                        sel.append(f["id"])
                    elif not toggled and f["id"] in sel:
                        sel.remove(f["id"])
                st.session_state["s2_selected_feature_ids"] = sel
                # Sync individual checkbox widget states
                for f in feats:
                    st.session_state[f"s2_feat_{f['id']}"] = toggled

            st.checkbox(
                f"Select all in {cat}",
                value=cat_all_selected,
                key=f"s2_cat_all_{cat}",
                on_change=_on_cat_toggle,
            )

            for feat in cat_features:
                cols = st.columns([0.05, 0.4, 0.15, 0.15, 0.25])
                is_selected = feat["id"] in selected_ids
                chk = cols[0].checkbox(
                    "",
                    value=is_selected,
                    key=f"s2_feat_{feat['id']}",
                    label_visibility="collapsed",
                )
                if chk != is_selected:
                    if chk:
                        selected_ids.append(feat["id"])
                    else:
                        if feat["id"] in selected_ids:
                            selected_ids.remove(feat["id"])
                        if feat["id"] in new_ids:
                            new_ids.remove(feat["id"])
                    changed = True

                cols[1].markdown(f"**{feat['name']}**" + (f"  \n_{feat['description'][:60]}..._" if len(feat["description"]) > 60 else (f"  \n_{feat['description']}_" if feat["description"] else "")))
                cols[2].markdown(f"`x{feat['complexity_weight']:.1f}`")
                existing_label = "Has tests" if feat["has_existing_tests"] else "No tests"
                cols[3].markdown(f"{'🟢' if feat['has_existing_tests'] else '🔴'} {existing_label}")

                # New / study toggle (only relevant for non-NEW projects; for NEW it's always flagged)
                if project_type != "NEW" and feat["id"] in selected_ids:
                    is_new_flag = feat["id"] in new_ids
                    new_toggle = cols[4].checkbox(
                        "Flag as new",
                        value=is_new_flag,
                        key=f"s2_new_{feat['id']}",
                    )
                    if new_toggle != is_new_flag:
                        if new_toggle:
                            new_ids.append(feat["id"])
                        else:
                            if feat["id"] in new_ids:
                                new_ids.remove(feat["id"])
                        changed = True
                elif project_type == "NEW" and feat["id"] in selected_ids:
                    cols[4].markdown("_Study (auto)_")

    st.session_state["s2_selected_feature_ids"] = selected_ids
    if project_type == "NEW":
        st.session_state["s2_new_feature_ids"] = selected_ids
    else:
        st.session_state["s2_new_feature_ids"] = new_ids

    total_sel = len(selected_ids)
    total_new = len(st.session_state["s2_new_feature_ids"])
    st.markdown(f"**Selected:** {total_sel} feature(s) — {total_new} flagged as new")
    return True


def render_step3() -> None:
    st.subheader("Step 3 — Reference Projects")
    st.caption(
        "Link historical projects to calibrate the estimation. "
        "The accuracy ratio (actual / estimated) and feature overlap are shown to help you choose relevant baselines."
    )

    projects = load_historical_projects()
    current_feature_ids = set(st.session_state["s2_selected_feature_ids"])
    selected_ref_ids: list[int] = list(st.session_state["s3_reference_project_ids"])

    if not projects:
        st.info("No historical projects found. You can proceed without reference projects, but risk flags may be raised.")
        return True

    col_search, col_type = st.columns([2, 1])
    ref_search = col_search.text_input("Search projects", placeholder="Filter by name...", key="s3_search")
    type_filter = col_type.selectbox("Type filter", options=["All", "NEW", "EVOLUTION", "SUPPORT"], key="s3_type_filter")

    filtered = [
        p for p in projects
        if (not ref_search or ref_search.lower() in p["project_name"].lower())
        and (type_filter == "All" or p["project_type"] == type_filter)
    ]

    if not filtered:
        st.info("No projects match the current filter.")
        return True

    # Table header
    hcols = st.columns([0.05, 0.25, 0.1, 0.12, 0.12, 0.12, 0.12, 0.12])
    for col, label in zip(hcols, ["", "Project", "Type", "Estimated h", "Actual h", "Ratio", "Overlap %", "Completion"]):
        col.markdown(f"**{label}**")
    st.divider()

    for proj in filtered:
        is_selected = proj["id"] in selected_ref_ids
        est = proj["estimated_hours"] or 0
        act = proj["actual_hours"] or 0
        ratio = act / est if est > 0 else None
        ratio_str = f"{ratio:.2f}" if ratio is not None else "N/A"
        ratio_colour = (
            "normal" if ratio is None
            else ("green" if ratio <= 1.0 else ("orange" if ratio <= 1.3 else "red"))
        )

        # Feature overlap
        try:
            ref_feat_ids = set(json.loads(proj["features_json"]))
        except Exception:
            ref_feat_ids = set()
        overlap = (len(current_feature_ids & ref_feat_ids) / len(current_feature_ids) * 100) if current_feature_ids else 0

        rcols = st.columns([0.05, 0.25, 0.1, 0.12, 0.12, 0.12, 0.12, 0.12])
        chk = rcols[0].checkbox("", value=is_selected, key=f"s3_ref_{proj['id']}", label_visibility="collapsed")
        if chk != is_selected:
            if chk:
                selected_ref_ids.append(proj["id"])
            else:
                selected_ref_ids.remove(proj["id"])

        rcols[1].write(proj["project_name"])
        rcols[2].write(proj["project_type"])
        rcols[3].write(f"{est:.0f}" if est else "-")
        rcols[4].write(f"{act:.0f}" if act else "-")
        rcols[5].markdown(f":{ratio_colour}[{ratio_str}]")
        rcols[6].write(f"{overlap:.0f}%")
        rcols[7].write(str(proj["completion_date"]) if proj["completion_date"] else "-")

    st.session_state["s3_reference_project_ids"] = selected_ref_ids

    if selected_ref_ids:
        # Show calibration preview
        selected_proj_data = [p for p in projects if p["id"] in selected_ref_ids]
        calib_data = [
            HistoricalDataPoint(
                project_name=p["project_name"],
                estimated_hours=p["estimated_hours"] or 0,
                actual_hours=p["actual_hours"] or 0,
                feature_ids=json.loads(p["features_json"]),
            )
            for p in selected_proj_data
            if (p["estimated_hours"] or 0) > 0
        ]
        if calib_data:
            calib = calibrate(calib_data, list(current_feature_ids))
            if calib.should_warn:
                st.warning(f"Calibration: {calib.message}")
            else:
                st.success(f"Calibration: {calib.message}")
        st.info(f"{len(selected_ref_ids)} reference project(s) selected.")
    else:
        st.warning("No reference projects selected. The estimation will have a 'no baseline' risk flag.")

    return True


def render_step4() -> None:
    st.subheader("Step 4 — DUT & Profile Matrix")
    st.caption(
        "Select the Device Under Test (DUT) types and test profiles. "
        "Then define which DUT-profile combinations are active."
    )

    dut_types = load_dut_types()
    test_profiles = load_test_profiles()

    if not dut_types or not test_profiles:
        st.warning("No DUT types or test profiles found. Add them via DUT Registry / Profiles pages.")
        st.info("The estimation will default to 1 DUT and 1 profile (no scaling applied).")
        return True

    col_dut, col_prof = st.columns(2)

    with col_dut:
        st.markdown("**Device Under Test (DUT) types**")
        dut_cats = sorted(set(d["category"] for d in dut_types))
        selected_dut_ids: list[int] = list(st.session_state["s4_selected_dut_ids"])

        for cat in dut_cats:
            cat_duts = [d for d in dut_types if d["category"] == cat]
            with st.expander(cat, expanded=True):
                for dut in cat_duts:
                    is_sel = dut["id"] in selected_dut_ids
                    chk = st.checkbox(
                        f"{dut['name']}  (×{dut['complexity_multiplier']:.2f})",
                        value=is_sel,
                        key=f"s4_dut_{dut['id']}",
                    )
                    if chk != is_sel:
                        if chk:
                            selected_dut_ids.append(dut["id"])
                        else:
                            selected_dut_ids.remove(dut["id"])
                            # Remove associated combinations
                            st.session_state["s4_combinations"] = [
                                c for c in st.session_state["s4_combinations"]
                                if c[0] != dut["id"]
                            ]

        st.session_state["s4_selected_dut_ids"] = selected_dut_ids
        st.caption(f"{len(selected_dut_ids)} DUT type(s) selected")

    with col_prof:
        st.markdown("**Test profiles**")
        selected_profile_ids: list[int] = list(st.session_state["s4_selected_profile_ids"])

        for prof in test_profiles:
            is_sel = prof["id"] in selected_profile_ids
            chk = st.checkbox(
                f"{prof['name']}  (×{prof['effort_multiplier']:.2f})"
                + (f"  — {prof['description'][:50]}" if prof["description"] else ""),
                value=is_sel,
                key=f"s4_prof_{prof['id']}",
            )
            if chk != is_sel:
                if chk:
                    selected_profile_ids.append(prof["id"])
                else:
                    selected_profile_ids.remove(prof["id"])
                    st.session_state["s4_combinations"] = [
                        c for c in st.session_state["s4_combinations"]
                        if c[1] != prof["id"]
                    ]

        st.session_state["s4_selected_profile_ids"] = selected_profile_ids
        st.caption(f"{len(selected_profile_ids)} profile(s) selected")

    # Combination matrix
    s_dut_ids = st.session_state["s4_selected_dut_ids"]
    s_prof_ids = st.session_state["s4_selected_profile_ids"]

    if s_dut_ids and s_prof_ids:
        st.markdown("---")
        st.markdown("**Active DUT × Profile combinations**")
        st.caption(
            "Check the combinations that will be tested. Each active combination counts toward the test matrix. "
            "By default all combinations are active."
        )

        # Initialise combinations to all-active if empty or stale
        existing_combos = set(map(tuple, st.session_state["s4_combinations"]))
        all_possible = {(d, p) for d in s_dut_ids for p in s_prof_ids}

        # Pre-fill: activate any new combinations not yet in state
        for combo in all_possible:
            if combo not in existing_combos:
                existing_combos.add(combo)
        # Prune combos that reference deselected DUTs/profiles
        existing_combos = {c for c in existing_combos if c[0] in s_dut_ids and c[1] in s_prof_ids}

        dut_map = {d["id"]: d for d in dut_types}
        prof_map = {p["id"]: p for p in test_profiles}

        # Build matrix grid
        header_cols = st.columns([2] + [1] * len(s_prof_ids))
        header_cols[0].markdown("**DUT \\ Profile**")
        for j, pid in enumerate(s_prof_ids):
            header_cols[j + 1].markdown(f"**{prof_map[pid]['name']}**")

        updated_combos: set[tuple] = set()
        for did in s_dut_ids:
            row_cols = st.columns([2] + [1] * len(s_prof_ids))
            row_cols[0].markdown(f"{dut_map[did]['name']}")
            for j, pid in enumerate(s_prof_ids):
                combo = (did, pid)
                is_active = combo in existing_combos
                cell_chk = row_cols[j + 1].checkbox(
                    "",
                    value=is_active,
                    key=f"s4_combo_{did}_{pid}",
                    label_visibility="collapsed",
                )
                if cell_chk:
                    updated_combos.add(combo)

        st.session_state["s4_combinations"] = [list(c) for c in updated_combos]
        total_combos = len(updated_combos)
        st.success(f"**{total_combos}** active combination(s) — DUT count: {len(s_dut_ids)}, Profile count: {len(s_prof_ids)}")

        if total_combos > 20:
            st.warning(f"High matrix complexity: {total_combos} combinations may increase estimation uncertainty.")
    elif s_dut_ids or s_prof_ids:
        st.info("Select at least one DUT and one profile to configure the combination matrix.")

    return True


def render_step5() -> None:
    st.subheader("Step 5 — PR Fixes")
    st.caption(
        "Enter the number of PR fix verifications expected by complexity. "
        "Each fix is validated per DUT (i.e., the counts are multiplied by the DUT count)."
    )

    dut_count = max(len(st.session_state["s4_selected_dut_ids"]), 1)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("### Simple PRs")
        st.caption("~2h per fix per DUT")
        simple = st.number_input(
            "Count",
            min_value=0,
            max_value=500,
            value=st.session_state["s5_pr_simple"],
            step=1,
            key="s5_simple_input",
        )
        st.session_state["s5_pr_simple"] = int(simple)
        st.metric("Subtotal", f"{simple * 2 * dut_count:.0f}h")

    with col_b:
        st.markdown("### Medium PRs")
        st.caption("~4h per fix per DUT")
        medium = st.number_input(
            "Count",
            min_value=0,
            max_value=500,
            value=st.session_state["s5_pr_medium"],
            step=1,
            key="s5_medium_input",
        )
        st.session_state["s5_pr_medium"] = int(medium)
        st.metric("Subtotal", f"{medium * 4 * dut_count:.0f}h")

    with col_c:
        st.markdown("### Complex PRs")
        st.caption("~8h per fix per DUT")
        complex_ = st.number_input(
            "Count",
            min_value=0,
            max_value=500,
            value=st.session_state["s5_pr_complex"],
            step=1,
            key="s5_complex_input",
        )
        st.session_state["s5_pr_complex"] = int(complex_)
        st.metric("Subtotal", f"{complex_ * 8 * dut_count:.0f}h")

    total_pr_hours = (simple * 2 + medium * 4 + complex_ * 8) * dut_count
    total_fixes = simple + medium + complex_
    st.markdown("---")
    st.markdown(
        f"**Total PR fixes:** {total_fixes}  |  "
        f"**Total PR effort (after DUT scaling × {dut_count}):** {total_pr_hours:.0f}h"
    )

    return True


def render_step6() -> None:
    st.subheader("Step 6 — Delivery Date & Team")
    st.caption("Set the expected delivery date and team configuration to calculate capacity and feasibility.")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Schedule**")
        delivery_date = st.date_input(
            "Expected delivery date",
            value=st.session_state["s6_delivery_date"],
            min_value=date.today(),
            key="s6_delivery_date_input",
        )
        st.session_state["s6_delivery_date"] = delivery_date

        days_remaining = (delivery_date - date.today()).days
        if days_remaining < 14:
            st.warning(f"Only {days_remaining} calendar days until delivery — compressed timeline risk.")
        else:
            st.info(f"{days_remaining} calendar days until delivery date.")

        working_days = st.number_input(
            "Working days available",
            min_value=1,
            max_value=365,
            value=st.session_state["s6_working_days"],
            step=1,
            key="s6_working_days_input",
            help="Total working days in the project window (excludes weekends/holidays).",
        )
        st.session_state["s6_working_days"] = int(working_days)

    with col_b:
        st.markdown("**Team**")
        team_size = st.number_input(
            "Number of testers",
            min_value=1,
            max_value=20,
            value=st.session_state["s6_team_size"],
            step=1,
            key="s6_team_size_input",
        )
        st.session_state["s6_team_size"] = int(team_size)

        has_leader = st.toggle(
            "Include test leader",
            value=st.session_state["s6_has_leader"],
            key="s6_has_leader_toggle",
            help="When enabled, adds 50% of tester hours as leader effort.",
        )
        st.session_state["s6_has_leader"] = has_leader

        total_people = team_size + (1 if has_leader else 0)
        capacity = int(working_days) * total_people * 7.0
        st.metric("Estimated capacity", f"{capacity:.0f}h", help="working_days × team_size × 7h/day")

        st.markdown("---")
        st.markdown(f"**Team composition:**")
        st.markdown(f"- {int(team_size)} tester(s)")
        if has_leader:
            st.markdown("- 1 test leader (leader effort = 50% of tester effort)")
        st.markdown(f"- {int(working_days)} working days")
        st.markdown(f"- 7.0 hours per day (default)")

    return True


def render_step7() -> None:
    st.subheader("Step 7 — Review & Generate Estimation")
    st.caption("Review the full breakdown, feasibility assessment, and risk flags. Save the estimation to the database or download reports.")

    # Run/refresh calculation
    if st.button("Calculate / Refresh", type="secondary", key="s7_calc_btn"):
        with st.spinner("Running estimation engine..."):
            _run_calculation()

    if st.session_state["calc_result"] is None:
        with st.spinner("Running estimation engine..."):
            _run_calculation()

    result = st.session_state["calc_result"]
    risk = st.session_state["risk_result"]
    calibration = st.session_state["calibration_result"]

    if result is None:
        st.error("Calculation failed. Please check your inputs and try again.")
        return True

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown("### Effort Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tester Hours", f"{result.total_tester_hours:.1f}h")
    m2.metric("Leader Hours", f"{result.total_leader_hours:.1f}h")
    m3.metric("PR Fix Hours", f"{result.pr_fix_hours:.1f}h")
    m4.metric("Study Hours", f"{result.study_hours:.1f}h")
    m5.metric("Buffer (10%)", f"{result.buffer_hours:.1f}h")

    st.markdown("---")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Grand Total", f"{result.grand_total_hours:.1f}h", delta=None)
    g2.metric("Person-Days", f"{result.grand_total_days:.1f}d")
    g3.metric("Capacity", f"{result.capacity_hours:.0f}h")
    g4.metric("Utilization", f"{result.utilization_pct:.1f}%")

    # ── Feasibility badge ─────────────────────────────────────────────────────
    st.markdown("### Feasibility")
    status = result.feasibility_status
    if status == "FEASIBLE":
        st.success(f"Status: {_feasibility_badge(status)} — The estimation fits within available team capacity.")
    elif status == "AT_RISK":
        st.warning(f"Status: {_feasibility_badge(status)} — The estimation is close to capacity limits.")
    else:
        st.error(f"Status: {_feasibility_badge(status)} — The estimation exceeds available capacity.")

    # ── Risk flags ────────────────────────────────────────────────────────────
    if risk and risk.flags:
        st.markdown("### Risk Flags")
        for msg in risk.messages:
            st.warning(f"**Risk:** {msg}")

    if calibration:
        if calibration.should_warn:
            st.warning(f"**Calibration warning:** {calibration.message}")
        else:
            st.info(f"**Calibration:** {calibration.message}")

    # ── Task breakdown ────────────────────────────────────────────────────────
    with st.expander("Full task breakdown", expanded=False):
        if result.tasks:
            task_data = [
                {
                    "Task": t.name,
                    "Type": t.task_type,
                    "Base (h)": round(t.base_hours, 2),
                    "DUT x": t.dut_multiplier,
                    "Profile x": t.profile_multiplier,
                    "Complexity": t.complexity_weight,
                    "Calculated (h)": round(t.calculated_hours, 2),
                    "Study?": "Yes" if t.is_new_feature_study else "",
                }
                for t in result.tasks
            ]
            st.dataframe(task_data, use_container_width=True, hide_index=True)
        else:
            st.info("No tasks generated. Ensure features with task templates are selected in Step 2.")

    # ── Project summary recap ─────────────────────────────────────────────────
    with st.expander("Project configuration recap", expanded=False):
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown(f"**Project name:** {st.session_state['s1_project_name']}")
            st.markdown(f"**Project type:** {st.session_state['s1_project_type']}")
            st.markdown(f"**Features selected:** {len(st.session_state['s2_selected_feature_ids'])}")
            st.markdown(f"**New features:** {len(st.session_state['s2_new_feature_ids'])}")
            st.markdown(f"**Reference projects:** {len(st.session_state['s3_reference_project_ids'])}")
        with col_r2:
            dut_count = max(len(st.session_state["s4_selected_dut_ids"]), 1)
            profile_count = max(len(st.session_state["s4_selected_profile_ids"]), 1)
            combos = len(st.session_state["s4_combinations"]) if st.session_state["s4_combinations"] else dut_count * profile_count
            st.markdown(f"**DUT types:** {dut_count}")
            st.markdown(f"**Test profiles:** {profile_count}")
            st.markdown(f"**DUT × Profile combinations:** {combos}")
            st.markdown(f"**PR fixes:** Simple={st.session_state['s5_pr_simple']}, Medium={st.session_state['s5_pr_medium']}, Complex={st.session_state['s5_pr_complex']}")
            st.markdown(f"**Team:** {st.session_state['s6_team_size']} tester(s)" + (" + 1 leader" if st.session_state["s6_has_leader"] else ""))
            st.markdown(f"**Working days:** {st.session_state['s6_working_days']}")
            st.markdown(f"**Delivery:** {st.session_state['s6_delivery_date']}")

    # ── Save & Download ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Save & Download")

    save_col, excel_col, word_col = st.columns(3)

    with save_col:
        if st.session_state["saved_estimation_id"]:
            st.success(f"Saved as EST-{date.today().year}-{st.session_state['saved_estimation_id']:04d}")
            if st.button("Save again (update)", key="s7_resave_btn"):
                try:
                    est_id = _save_to_database()
                    st.success(f"Estimation saved: EST-{date.today().year}-{est_id:04d}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
        else:
            if not st.session_state["s1_project_name"].strip():
                st.error("Set a project name in Step 1 before saving.")
            else:
                if st.button("Save to database", type="primary", key="s7_save_btn"):
                    try:
                        est_id = _save_to_database()
                        st.success(f"Estimation saved: EST-{date.today().year}-{est_id:04d}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Save failed: {exc}")

    with excel_col:
        try:
            report_data = _build_report_data()
            excel_bytes = generate_excel_report(report_data)
            if excel_bytes:
                project_slug = (st.session_state["s1_project_name"] or "estimation").replace(" ", "_")[:40]
                st.download_button(
                    label="Download Excel report",
                    data=excel_bytes,
                    file_name=f"{project_slug}_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="s7_excel_btn",
                )
        except Exception as exc:
            st.error(f"Excel generation failed: {exc}")

    with word_col:
        try:
            report_data = _build_report_data()
            word_bytes = generate_word_report(report_data)
            if word_bytes:
                project_slug = (st.session_state["s1_project_name"] or "estimation").replace(" ", "_")[:40]
                st.download_button(
                    label="Download Word report",
                    data=word_bytes,
                    file_name=f"{project_slug}_{date.today()}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="s7_word_btn",
                )
        except Exception as exc:
            st.error(f"Word generation failed: {exc}")

    return True


# ── Step definitions ──────────────────────────────────────────────────────────

STEP_LABELS = [
    "1. Request",
    "2. Features",
    "3. References",
    "4. DUT & Profiles",
    "5. PR Fixes",
    "6. Team & Date",
    "7. Review",
]

STEP_RENDERERS = [
    render_step1,
    render_step2,
    render_step3,
    render_step4,
    render_step5,
    render_step6,
    render_step7,
]

# ── Main layout ───────────────────────────────────────────────────────────────

_is_edit_mode = "_edit_estimation_id" in st.session_state
if _is_edit_mode:
    _edit_ver = st.session_state.get("_edit_estimation_version", 1)
    st.title(f"Edit Estimation (v{_edit_ver} → v{_edit_ver + 1})")
    st.markdown("Revise the inputs below. Saving will create a new version and reset status to DRAFT.")
else:
    st.title("New Estimation")
    st.markdown("Complete the 7 steps below to build a test effort estimation. All inputs are preserved as you move between steps.")

# Reset button in sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("**Estimation Wizard**")
    if st.button("Reset wizard", help="Clear all wizard inputs and start fresh"):
        for key in list(WIZARD_DEFAULTS.keys()):
            st.session_state[key] = WIZARD_DEFAULTS[key]
        # Clear edit mode if active
        st.session_state.pop("_edit_estimation_id", None)
        st.session_state.pop("_edit_estimation_version", None)
        # Also clear caches so DB reload happens
        load_features.clear()
        load_dut_types.clear()
        load_test_profiles.clear()
        load_historical_projects.clear()
        load_requests.clear()
        load_task_templates.clear()
        st.rerun()

    if st.session_state["saved_estimation_id"]:
        st.success(
            f"Saved: EST-{date.today().year}-{st.session_state['saved_estimation_id']:04d}"
        )

# Tabs for the 7 steps
tabs = st.tabs(STEP_LABELS)

for idx, (tab, renderer) in enumerate(zip(tabs, STEP_RENDERERS)):
    with tab:
        renderer()
