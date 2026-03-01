"""FastAPI REST endpoints for all entities."""

import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database.models import (
    Configuration,
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
    DutTypeCreate,
    DutTypeOut,
    DutTypeUpdate,
    EstimationCreate,
    EstimationOut,
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
    TaskTemplateCreate,
    TaskTemplateOut,
    TaskTemplateUpdate,
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberUpdate,
    TestProfileCreate,
    TestProfileOut,
    TestProfileUpdate,
)

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


# ── Features ─────────────────────────────────────────────

@router.get("/features", response_model=list[FeatureOut])
def list_features(db: Session = Depends(get_db)):
    return db.query(Feature).all()


@router.post("/features", response_model=FeatureOut, status_code=201)
def create_feature(data: FeatureCreate, db: Session = Depends(get_db)):
    feature = Feature(**data.model_dump())
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature


@router.get("/features/{feature_id}", response_model=FeatureOut)
def get_feature(feature_id: int, db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    return feature


@router.put("/features/{feature_id}", response_model=FeatureOut)
def update_feature(feature_id: int, data: FeatureUpdate, db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(feature, key, val)
    db.commit()
    db.refresh(feature)
    return feature


@router.delete("/features/{feature_id}", status_code=204)
def delete_feature(feature_id: int, db: Session = Depends(get_db)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    db.delete(feature)
    db.commit()


# ── Task Templates ───────────────────────────────────────

@router.get("/task-templates", response_model=list[TaskTemplateOut])
def list_task_templates(feature_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(TaskTemplate)
    if feature_id is not None:
        q = q.filter(TaskTemplate.feature_id == feature_id)
    return q.all()


@router.post("/task-templates", response_model=TaskTemplateOut, status_code=201)
def create_task_template(data: TaskTemplateCreate, db: Session = Depends(get_db)):
    tmpl = TaskTemplate(**data.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.put("/task-templates/{template_id}", response_model=TaskTemplateOut)
def update_task_template(template_id: int, data: TaskTemplateUpdate, db: Session = Depends(get_db)):
    tmpl = db.get(TaskTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Task template not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(tmpl, key, val)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.delete("/task-templates/{template_id}", status_code=204)
def delete_task_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.get(TaskTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Task template not found")
    db.delete(tmpl)
    db.commit()


# ── DUT Types ────────────────────────────────────────────

@router.get("/dut-types", response_model=list[DutTypeOut])
def list_dut_types(db: Session = Depends(get_db)):
    return db.query(DutType).all()


@router.post("/dut-types", response_model=DutTypeOut, status_code=201)
def create_dut_type(data: DutTypeCreate, db: Session = Depends(get_db)):
    dut = DutType(**data.model_dump())
    db.add(dut)
    db.commit()
    db.refresh(dut)
    return dut


@router.put("/dut-types/{dut_id}", response_model=DutTypeOut)
def update_dut_type(dut_id: int, data: DutTypeUpdate, db: Session = Depends(get_db)):
    dut = db.get(DutType, dut_id)
    if not dut:
        raise HTTPException(404, "DUT type not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(dut, key, val)
    db.commit()
    db.refresh(dut)
    return dut


@router.delete("/dut-types/{dut_id}", status_code=204)
def delete_dut_type(dut_id: int, db: Session = Depends(get_db)):
    dut = db.get(DutType, dut_id)
    if not dut:
        raise HTTPException(404, "DUT type not found")
    db.delete(dut)
    db.commit()


# ── Test Profiles ────────────────────────────────────────

@router.get("/profiles", response_model=list[TestProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return db.query(TestProfile).all()


@router.post("/profiles", response_model=TestProfileOut, status_code=201)
def create_profile(data: TestProfileCreate, db: Session = Depends(get_db)):
    profile = TestProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/profiles/{profile_id}", response_model=TestProfileOut)
def update_profile(profile_id: int, data: TestProfileUpdate, db: Session = Depends(get_db)):
    profile = db.get(TestProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.get(TestProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()


# ── Historical Projects ──────────────────────────────────

@router.get("/historical-projects", response_model=list[HistoricalProjectOut])
def list_historical_projects(db: Session = Depends(get_db)):
    return db.query(HistoricalProject).all()


@router.post("/historical-projects", response_model=HistoricalProjectOut, status_code=201)
def create_historical_project(data: HistoricalProjectCreate, db: Session = Depends(get_db)):
    proj = HistoricalProject(**data.model_dump())
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


# ── Team Members ─────────────────────────────────────────

@router.get("/team-members", response_model=list[TeamMemberOut])
def list_team_members(db: Session = Depends(get_db)):
    return db.query(TeamMember).all()


@router.post("/team-members", response_model=TeamMemberOut, status_code=201)
def create_team_member(data: TeamMemberCreate, db: Session = Depends(get_db)):
    member = TeamMember(**data.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/team-members/{member_id}", response_model=TeamMemberOut)
def update_team_member(member_id: int, data: TeamMemberUpdate, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(member, key, val)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/team-members/{member_id}", status_code=204)
def delete_team_member(member_id: int, db: Session = Depends(get_db)):
    member = db.get(TeamMember, member_id)
    if not member:
        raise HTTPException(404, "Team member not found")
    db.delete(member)
    db.commit()


# ── Requests ─────────────────────────────────────────────

@router.get("/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Request)
    if status:
        q = q.filter(Request.status == status)
    return q.order_by(Request.created_at.desc()).all()


@router.post("/requests", response_model=RequestOut, status_code=201)
def create_request(data: RequestCreate, db: Session = Depends(get_db)):
    req_data = data.model_dump()
    req = Request(**req_data)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db)):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    return req


@router.put("/requests/{request_id}", response_model=RequestOut)
def update_request(request_id: int, data: RequestUpdate, db: Session = Depends(get_db)):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(req, key, val)
    db.commit()
    db.refresh(req)
    return req


# ── Configuration ────────────────────────────────────────

@router.get("/configuration", response_model=list[ConfigurationOut])
def list_configuration(db: Session = Depends(get_db)):
    return db.query(Configuration).all()


@router.put("/configuration/{key}", response_model=ConfigurationOut)
def update_configuration(key: str, data: ConfigurationUpdate, db: Session = Depends(get_db)):
    cfg = db.get(Configuration, key)
    if not cfg:
        raise HTTPException(404, "Configuration key not found")
    cfg.value = data.value
    db.commit()
    db.refresh(cfg)
    return cfg


# ── Estimations ──────────────────────────────────────────

@router.post("/estimations/calculate", response_model=CalculationResultOut)
def calculate_estimation_preview(data: CalculateInput, db: Session = Depends(get_db)):
    """Run calculation from wizard inputs without persisting to DB."""
    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))

    feature_ids = data.resolved_feature_ids
    new_feature_ids = data.resolved_new_feature_ids
    delivery = data.expected_delivery or data.delivery_date

    features = db.query(Feature).filter(Feature.id.in_(feature_ids)).all()
    templates = db.query(TaskTemplate).filter(
        (TaskTemplate.feature_id.in_(feature_ids)) | (TaskTemplate.feature_id.is_(None))
    ).all()

    task_inputs: list[TaskInput] = []
    for tmpl in templates:
        feature = next((f for f in features if f.id == tmpl.feature_id), None)
        cw = feature.complexity_weight if feature else 1.0
        is_study = tmpl.feature_id is not None and tmpl.feature_id in new_feature_ids
        task_inputs.append(TaskInput(
            name=tmpl.name,
            task_type=tmpl.task_type,
            base_effort_hours=tmpl.base_effort_hours,
            scales_with_dut=tmpl.scales_with_dut,
            scales_with_profile=tmpl.scales_with_profile,
            complexity_weight=cw,
            is_new_feature_study=is_study,
            template_id=tmpl.id,
        ))

    dut_count = len(data.dut_ids) if data.dut_ids else 1
    profile_count = len(data.profile_ids) if data.profile_ids else 1
    new_feature_count = len(new_feature_ids)

    calc_input = EstimationInput(
        project_type=data.project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        pr_fixes=CalcPRFixInput(
            simple=data.pr_fixes.simple,
            medium=data.pr_fixes.medium,
            complex=data.pr_fixes.complex_,
        ),
        new_feature_count=new_feature_count,
        team_size=data.team_size,
        has_leader=data.has_leader,
        working_days=data.working_days,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
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

    return CalculationResultOut(
        tasks=[
            {
                "name": t.name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "calculated_hours": t.calculated_hours,
            }
            for t in result.tasks
        ],
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        pr_fix_hours=result.pr_fix_hours,
        study_hours=result.study_hours,
        buffer_hours=result.buffer_hours,
        grand_total_hours=result.grand_total_hours,
        grand_total_days=result.grand_total_days,
        feasibility_status=result.feasibility_status,
        capacity_hours=result.capacity_hours,
        utilization_pct=result.utilization_pct,
        risk_flags=[f.value for f in risks.flags],
        risk_messages=risks.messages,
    )


@router.get("/estimations", response_model=list[EstimationOut])
def list_estimations(db: Session = Depends(get_db)):
    return db.query(Estimation).order_by(Estimation.created_at.desc()).all()


@router.get("/estimations/{estimation_id}", response_model=EstimationOut)
def get_estimation(estimation_id: int, db: Session = Depends(get_db)):
    est = db.get(Estimation, estimation_id)
    if not est:
        raise HTTPException(404, "Estimation not found")
    return est


@router.post("/estimations", response_model=EstimationOut, status_code=201)
def create_estimation(data: EstimationCreate, db: Session = Depends(get_db)):
    """Create a new estimation: resolve inputs, run calculation, save result."""
    # Resolve config
    leader_ratio = float(_get_config_value(db, "leader_effort_ratio", "0.5"))
    study_hours_cfg = float(_get_config_value(db, "new_feature_study_hours", "16.0"))
    hours_per_day = float(_get_config_value(db, "working_hours_per_day", "7.0"))
    buffer_pct = float(_get_config_value(db, "buffer_percentage", "10"))

    # Resolve features and their task templates
    features = db.query(Feature).filter(Feature.id.in_(data.feature_ids)).all()
    templates = db.query(TaskTemplate).filter(
        (TaskTemplate.feature_id.in_(data.feature_ids)) | (TaskTemplate.feature_id.is_(None))
    ).all()

    # Build task inputs
    task_inputs: list[TaskInput] = []
    for tmpl in templates:
        feature = next((f for f in features if f.id == tmpl.feature_id), None)
        cw = feature.complexity_weight if feature else 1.0
        is_study = tmpl.id is not None and tmpl.feature_id is not None and tmpl.feature_id in data.new_feature_ids
        task_inputs.append(TaskInput(
            name=tmpl.name,
            task_type=tmpl.task_type,
            base_effort_hours=tmpl.base_effort_hours,
            scales_with_dut=tmpl.scales_with_dut,
            scales_with_profile=tmpl.scales_with_profile,
            complexity_weight=cw,
            is_new_feature_study=is_study,
            template_id=tmpl.id,
        ))

    dut_count = len(data.dut_ids) if data.dut_ids else 1
    profile_count = len(data.profile_ids) if data.profile_ids else 1
    combinations = len(data.dut_profile_matrix) if data.dut_profile_matrix else dut_count * profile_count
    new_feature_count = len(data.new_feature_ids)
    pr_total = data.pr_fixes.simple + data.pr_fixes.medium + data.pr_fixes.complex_

    # Run calculation
    calc_input = EstimationInput(
        project_type=data.project_type,
        tasks=task_inputs,
        dut_count=dut_count,
        profile_count=profile_count,
        pr_fixes=CalcPRFixInput(
            simple=data.pr_fixes.simple,
            medium=data.pr_fixes.medium,
            complex=data.pr_fixes.complex_,
        ),
        new_feature_count=new_feature_count,
        team_size=data.team_size,
        has_leader=data.has_leader,
        working_days=data.working_days,
        leader_effort_ratio=leader_ratio,
        new_feature_study_hours=study_hours_cfg,
        working_hours_per_day=hours_per_day,
        buffer_percentage=buffer_pct,
    )
    result = calculate_estimation(calc_input)

    # Generate estimation number
    est_number = _generate_number(db, "estimation_number_prefix", Estimation, "estimation_number")

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
        expected_delivery=data.expected_delivery,
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        grand_total_hours=result.grand_total_hours,
        grand_total_days=result.grand_total_days,
        feasibility_status=result.feasibility_status,
        status="DRAFT",
        created_by=data.created_by,
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
            assigned_testers=1,
            has_leader_support=data.has_leader,
            leader_hours=task.calculated_hours * leader_ratio if data.has_leader else 0,
            is_new_feature_study=task.is_new_feature_study,
        )
        db.add(et)

    # Update request status if linked
    if data.request_id:
        req = db.get(Request, data.request_id)
        if req:
            req.status = "ESTIMATED"

    db.commit()
    db.refresh(estimation)
    return estimation


@router.post("/estimations/{estimation_id}/calculate", response_model=CalculationResultOut)
def recalculate_estimation(estimation_id: int, db: Session = Depends(get_db)):
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

    return CalculationResultOut(
        tasks=[
            {
                "name": t.name,
                "task_type": t.task_type,
                "base_hours": t.base_hours,
                "calculated_hours": t.calculated_hours,
            }
            for t in result.tasks
        ],
        total_tester_hours=result.total_tester_hours,
        total_leader_hours=result.total_leader_hours,
        pr_fix_hours=result.pr_fix_hours,
        study_hours=result.study_hours,
        buffer_hours=result.buffer_hours,
        grand_total_hours=result.grand_total_hours,
        grand_total_days=result.grand_total_days,
        feasibility_status=result.feasibility_status,
        capacity_hours=result.capacity_hours,
        utilization_pct=result.utilization_pct,
        risk_flags=[f.value for f in risks.flags],
        risk_messages=risks.messages,
    )


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


@router.get("/estimations/{estimation_id}/report/xlsx")
def download_excel_report(estimation_id: int, db: Session = Depends(get_db)):
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
def download_word_report(estimation_id: int, db: Session = Depends(get_db)):
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
def download_pdf_report(estimation_id: int, db: Session = Depends(get_db)):
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
def list_integrations(db: Session = Depends(get_db)) -> list[dict]:
    configs = db.query(IntegrationConfig).all()
    return [IntegrationConfigOut.from_model(c).model_dump() for c in configs]


@router.get("/integrations/{system_name}")
def get_integration(system_name: str, db: Session = Depends(get_db)) -> dict:
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == system_name.upper()).first()
    if not cfg:
        raise HTTPException(404, f"Integration {system_name} not found")
    return IntegrationConfigOut.from_model(cfg).model_dump()


@router.put("/integrations/{system_name}")
def update_integration(system_name: str, data: IntegrationConfigUpdate, db: Session = Depends(get_db)) -> dict:
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
def test_integration_endpoint(system_name: str, db: Session = Depends(get_db)) -> dict:
    from ..integrations.service import test_integration
    result = test_integration(system_name.upper(), db)
    return ConnectionTestOut(
        success=result.success,
        message=result.message,
        details=result.details,
    ).model_dump()


@router.post("/integrations/{system_name}/sync")
def trigger_sync(system_name: str, db: Session = Depends(get_db)) -> dict:
    from ..integrations.service import sync_import
    result = sync_import(system_name.upper(), db)
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
def integration_health(system_name: str, db: Session = Depends(get_db)) -> dict:
    cfg = db.query(IntegrationConfig).filter(IntegrationConfig.system_name == system_name.upper()).first()
    if not cfg:
        raise HTTPException(404, f"Integration {system_name} not found")
    return {
        "system_name": cfg.system_name,
        "enabled": cfg.enabled,
        "last_sync_at": str(cfg.last_sync_at) if cfg.last_sync_at else None,
        "configured": bool(cfg.base_url or cfg.api_key),
    }


# ── Send report via email ────────────────────────────────

@router.post("/estimations/{estimation_id}/send-report")
def send_estimation_report(estimation_id: int, to_email: str, db: Session = Depends(get_db)) -> dict:
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
def update_estimation(estimation_id: int, data: EstimationUpdate, db: Session = Depends(get_db)):
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
def delete_estimation(estimation_id: int, db: Session = Depends(get_db)):
    estimation = db.get(Estimation, estimation_id)
    if not estimation:
        raise HTTPException(404, "Estimation not found")
    db.delete(estimation)
    db.commit()


@router.post("/estimations/{estimation_id}/status", response_model=EstimationOut)
def update_estimation_status(estimation_id: int, data: EstimationStatusUpdate, db: Session = Depends(get_db)):
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

    # Auto-export to external system when estimation is finalized or approved
    if target in ("FINAL", "APPROVED") and estimation.request_id:
        _try_export_estimation(estimation, db)

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
        }
        sync_export(req.request_source, estimation_data, db)
    except Exception:
        # Export failure should not block the status transition
        pass


@router.post("/estimations/{estimation_id}/export")
def export_estimation_to_external(estimation_id: int, db: Session = Depends(get_db)):
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
    }
    result = sync_export(req.request_source, estimation_data, db)

    return {
        "status": result.status.value,
        "system": result.system,
        "items_updated": result.items_updated,
        "errors": result.errors,
    }


# ── Request detail with linked estimations ───────────────

@router.get("/requests/{request_id}/detail", response_model=RequestDetailOut)
def get_request_detail(request_id: int, db: Session = Depends(get_db)):
    """Get request with all linked estimations."""
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    return req


# ── Request attachment upload ────────────────────────────

@router.post("/requests/{request_id}/attachments")
async def upload_attachment(request_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
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


# ── Calibration endpoint ────────────────────────────────

@router.post("/estimations/{estimation_id}/calibrate", response_model=CalibrationResultOut)
def calibrate_estimation(estimation_id: int, db: Session = Depends(get_db)):
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
def get_dashboard_stats(db: Session = Depends(get_db)):
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

    # Recent estimations (last 10)
    recent_est = db.query(Estimation).order_by(
        Estimation.created_at.desc()
    ).limit(10).all()
    recent_estimations = [
        RecentEstimationOut(
            id=e.id,
            estimation_number=e.estimation_number,
            project_name=e.project_name,
            grand_total_hours=round(e.grand_total_hours, 1),
            feasibility_status=e.feasibility_status,
            status=e.status,
            created_at=e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else None,
        )
        for e in recent_est
    ]

    # Recent requests (last 10)
    recent_req = db.query(Request).order_by(
        Request.created_at.desc()
    ).limit(10).all()
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
    )
