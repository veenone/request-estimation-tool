"""Pydantic request/response models for the FastAPI layer."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Features ──────────────────────────────────────────────

class FeatureBase(BaseModel):
    name: str
    category: Optional[str] = None
    complexity_weight: float = 1.0
    has_existing_tests: bool = False
    description: Optional[str] = None

class FeatureCreate(FeatureBase):
    pass

class FeatureUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    complexity_weight: Optional[float] = None
    has_existing_tests: Optional[bool] = None
    description: Optional[str] = None

class TaskTemplateOut(BaseModel):
    id: int
    feature_id: Optional[int] = None
    name: str
    task_type: str
    base_effort_hours: float
    scales_with_dut: bool
    scales_with_profile: bool
    is_parallelizable: bool
    description: Optional[str] = None

    model_config = {"from_attributes": True}

class FeatureOut(FeatureBase):
    id: int
    created_at: Optional[datetime] = None
    task_templates: list[TaskTemplateOut] = []

    model_config = {"from_attributes": True}


# ── Task Templates ────────────────────────────────────────

class TaskTemplateCreate(BaseModel):
    feature_id: Optional[int] = None
    name: str
    task_type: str
    base_effort_hours: float
    scales_with_dut: bool = False
    scales_with_profile: bool = False
    is_parallelizable: bool = False
    description: Optional[str] = None

class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = None
    task_type: Optional[str] = None
    base_effort_hours: Optional[float] = None
    scales_with_dut: Optional[bool] = None
    scales_with_profile: Optional[bool] = None
    is_parallelizable: Optional[bool] = None
    description: Optional[str] = None


# ── DUT Types ─────────────────────────────────────────────

class DutTypeBase(BaseModel):
    name: str
    category: Optional[str] = None
    complexity_multiplier: float = 1.0

class DutTypeCreate(DutTypeBase):
    pass

class DutTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    complexity_multiplier: Optional[float] = None

class DutTypeOut(DutTypeBase):
    id: int

    model_config = {"from_attributes": True}


# ── Test Profiles ─────────────────────────────────────────

class TestProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    effort_multiplier: float = 1.0

class TestProfileCreate(TestProfileBase):
    pass

class TestProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effort_multiplier: Optional[float] = None

class TestProfileOut(TestProfileBase):
    id: int

    model_config = {"from_attributes": True}


# ── Historical Projects ──────────────────────────────────

class HistoricalProjectBase(BaseModel):
    project_name: str
    project_type: str
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    dut_count: Optional[int] = None
    profile_count: Optional[int] = None
    pr_count: Optional[int] = None
    features_json: str = "[]"
    completion_date: Optional[date] = None
    notes: Optional[str] = None

class HistoricalProjectCreate(HistoricalProjectBase):
    pass

class HistoricalProjectOut(HistoricalProjectBase):
    id: int

    model_config = {"from_attributes": True}


# ── Team Members ─────────────────────────────────────────

class TeamMemberBase(BaseModel):
    name: str
    role: str
    available_hours_per_day: float = 7.0
    skills_json: str = "[]"

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    available_hours_per_day: Optional[float] = None
    skills_json: Optional[str] = None

class TeamMemberOut(TeamMemberBase):
    id: int

    model_config = {"from_attributes": True}


# ── Requests ─────────────────────────────────────────────

class RequestBase(BaseModel):
    request_number: str
    request_source: str = "MANUAL"
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    requester_name: str
    requester_email: Optional[str] = None
    business_unit: Optional[str] = None
    priority: str = "MEDIUM"
    requested_delivery_date: Optional[date] = None
    received_date: date
    notes: Optional[str] = None

class RequestCreate(RequestBase):
    pass

class RequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    business_unit: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    requested_delivery_date: Optional[date] = None
    notes: Optional[str] = None

class RequestOut(RequestBase):
    id: int
    status: str
    attachments_json: str = "[]"
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_assigned_to_name(cls, data, handler):
        obj = handler(data)
        if obj.assigned_to_name is None and hasattr(data, "assigned_to") and data.assigned_to is not None:
            obj.assigned_to_name = data.assigned_to.display_name or data.assigned_to.username
        return obj


# ── Configuration ────────────────────────────────────────

class ConfigurationOut(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}

class ConfigurationUpdate(BaseModel):
    value: str


# ── Estimations ──────────────────────────────────────────

class PRFixInput(BaseModel):
    simple: int = 0
    medium: int = 0
    complex_: int = Field(0, alias="complex")

    model_config = {"populate_by_name": True}

class EstimationTaskOut(BaseModel):
    id: int
    task_template_id: Optional[int] = None
    task_name: str
    task_type: str
    base_hours: float
    calculated_hours: float
    assigned_testers: int
    has_leader_support: bool
    leader_hours: float
    is_new_feature_study: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}

class CalculateInput(BaseModel):
    """Schema for calculation-only preview (no DB persistence)."""
    project_type: str
    features: list[int] = Field(default_factory=list, alias="feature_ids")
    new_features: list[int] = Field(default_factory=list, alias="new_feature_ids")
    reference_project_ids: list[int] = []
    dut_ids: list[int] = []
    profile_ids: list[int] = []
    dut_profile_matrix: list[list[int]] = []
    pr_fixes: PRFixInput = Field(default_factory=PRFixInput)
    team_size: int = 1
    has_leader: bool = False
    expected_delivery: Optional[date] = None
    working_days: int = 20
    delivery_date: Optional[date] = None

    model_config = {"populate_by_name": True}

    @property
    def resolved_feature_ids(self) -> list[int]:
        return self.features

    @property
    def resolved_new_feature_ids(self) -> list[int]:
        return self.new_features

class EstimationCreate(BaseModel):
    request_id: Optional[int] = None
    project_name: str
    project_type: str
    feature_ids: list[int] = []
    new_feature_ids: list[int] = []
    reference_project_ids: list[int] = []
    dut_ids: list[int] = []
    profile_ids: list[int] = []
    dut_profile_matrix: list[list[int]] = []
    pr_fixes: PRFixInput = Field(default_factory=PRFixInput)
    team_size: int = 1
    has_leader: bool = False
    expected_delivery: Optional[date] = None
    working_days: int = 20
    created_by: Optional[str] = None

class EstimationOut(BaseModel):
    id: int
    request_id: Optional[int] = None
    estimation_number: Optional[str] = None
    project_name: str
    project_type: str
    reference_project_ids: str = "[]"
    dut_count: int
    profile_count: int
    dut_profile_combinations: int
    pr_fix_count: int
    expected_delivery: Optional[date] = None
    total_tester_hours: float
    total_leader_hours: float
    grand_total_hours: float
    grand_total_days: float
    feasibility_status: str
    status: str
    version: int = 1
    wizard_inputs_json: str = "{}"
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    tasks: list[EstimationTaskOut] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_assigned_to_name(cls, data, handler):
        # When constructing from an ORM object, resolve the relationship
        obj = handler(data)
        if obj.assigned_to_name is None and hasattr(data, "assigned_to") and data.assigned_to is not None:
            obj.assigned_to_name = data.assigned_to.display_name or data.assigned_to.username
        return obj

class EstimationUpdate(BaseModel):
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    expected_delivery: Optional[date] = None
    notes: Optional[str] = None


class EstimationRevise(BaseModel):
    """Payload for revising an estimation — same wizard inputs as create, minus request/author."""
    project_name: str
    project_type: str
    feature_ids: list[int] = []
    new_feature_ids: list[int] = []
    reference_project_ids: list[int] = []
    dut_ids: list[int] = []
    profile_ids: list[int] = []
    dut_profile_matrix: list[list[int]] = []
    pr_fixes: PRFixInput = Field(default_factory=PRFixInput)
    team_size: int = 1
    has_leader: bool = False
    expected_delivery: Optional[date] = None
    working_days: int = 20


class EstimationStatusUpdate(BaseModel):
    status: str  # DRAFT, FINAL, APPROVED, REVISED
    approved_by: Optional[str] = None


class RequestDetailOut(RequestOut):
    """Extended request output including linked estimations."""
    estimations: list[EstimationOut] = []

    model_config = {"from_attributes": True}


class RecentEstimationOut(BaseModel):
    id: int
    estimation_number: Optional[str] = None
    project_name: str
    grand_total_hours: float = 0
    feasibility_status: str = ""
    status: str = ""
    version: int = 1
    created_at: Optional[str] = None

class RecentRequestOut(BaseModel):
    id: int
    request_number: str = ""
    title: str = ""
    priority: str = ""
    status: str = ""
    created_at: Optional[str] = None

class DashboardStatsOut(BaseModel):
    total_requests: int = 0
    requests_new: int = 0
    requests_in_progress: int = 0
    requests_completed: int = 0
    total_estimations: int = 0
    estimations_draft: int = 0
    estimations_final: int = 0
    estimations_approved: int = 0
    avg_grand_total_hours: float = 0
    avg_utilization_pct: float = 0
    recent_estimations: list[RecentEstimationOut] = []
    recent_requests: list[RecentRequestOut] = []


class CalibrationResultOut(BaseModel):
    accuracy_ratio: float
    adjustment_factor: float
    suggestion: str
    reference_projects: list[dict] = []
    adjusted_grand_total: float = 0


class CalculationResultOut(BaseModel):
    tasks: list[dict]
    total_tester_hours: float
    total_leader_hours: float
    pr_fix_hours: float
    study_hours: float
    buffer_hours: float
    grand_total_hours: float
    grand_total_days: float
    feasibility_status: str
    capacity_hours: float
    utilization_pct: float
    risk_flags: list[str] = []
    risk_messages: list[str] = []
