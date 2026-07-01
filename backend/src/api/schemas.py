"""Pydantic request/response models for the FastAPI layer."""

from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, Field, model_validator


def _coerce_date(v: object) -> object:
    """Accept ISO-format date strings so ``Optional[date]`` fields work in
    Pydantic v2 union resolution (which otherwise picks the ``None`` branch
    and rejects the string)."""
    if isinstance(v, str):
        v_stripped = v.strip()
        if v_stripped:
            return date.fromisoformat(v_stripped)
        return None
    return v


OptionalDate = Annotated[Optional[date], BeforeValidator(_coerce_date)]


# ── Features ──────────────────────────────────────────────

class FeatureBase(BaseModel):
    name: str
    category: Optional[str] = None
    complexity_weight: float = 1.0
    has_existing_tests: bool = False
    description: Optional[str] = None
    product_type: Optional[str] = None
    study_effort_hours: Optional[float] = None
    base_effort_hours: float = 0.0

class FeatureCreate(FeatureBase):
    pass

class FeaturePresetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    product_type: Optional[str] = None
    feature_ids: list[int] = []

class FeaturePresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    product_type: Optional[str] = None
    feature_ids: Optional[list[int]] = None

class FeaturePresetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    product_type: Optional[str] = None
    feature_ids: list[int] = []
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None

    model_config = {"from_attributes": True}

class FeatureUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    complexity_weight: Optional[float] = None
    has_existing_tests: Optional[bool] = None
    description: Optional[str] = None
    product_type: Optional[str] = None
    study_effort_hours: Optional[float] = None
    base_effort_hours: Optional[float] = None

class TaskTemplateOut(BaseModel):
    id: int
    feature_id: Optional[int] = None
    feature_ids: list[int] = []
    feature_hours: dict[str, float] = {}  # {feature_id_str: base_hours_override}
    name: str
    task_type: str
    base_effort_hours: float
    scales_with_dut: bool
    scales_with_profile: bool
    is_parallelizable: bool
    is_pr_fix: bool = False
    description: Optional[str] = None
    product_type: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_features(cls, data, handler):
        obj = handler(data)
        if not obj.feature_ids and hasattr(data, "features"):
            obj.feature_ids = [f.id for f in data.features]
        # Backward compat: set feature_id to first if exactly one
        if obj.feature_ids and obj.feature_id is None:
            obj.feature_id = obj.feature_ids[0] if len(obj.feature_ids) == 1 else None
        return obj

class FeatureOut(FeatureBase):
    id: int
    is_global: bool = True
    owner_estimation_id: Optional[int] = None
    promotion_requested: bool = False
    created_at: Optional[datetime] = None
    task_templates: list[TaskTemplateOut] = []

    model_config = {"from_attributes": True}


# ── Task Templates ────────────────────────────────────────

class TaskTemplateCreate(BaseModel):
    feature_id: Optional[int] = None  # Legacy single-feature (backward compat)
    feature_ids: list[int] = []  # Many-to-many feature IDs
    feature_hours: dict[str, float] = {}  # {feature_id_str: base_hours_override}
    name: str
    task_type: str
    base_effort_hours: float
    scales_with_dut: bool = False
    scales_with_profile: bool = False
    is_parallelizable: bool = False
    is_pr_fix: bool = False
    description: Optional[str] = None
    product_type: Optional[str] = None

class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = None
    task_type: Optional[str] = None
    base_effort_hours: Optional[float] = None
    scales_with_dut: Optional[bool] = None
    scales_with_profile: Optional[bool] = None
    is_parallelizable: Optional[bool] = None
    is_pr_fix: Optional[bool] = None
    description: Optional[str] = None
    product_type: Optional[str] = None
    feature_ids: Optional[list[int]] = None  # Many-to-many feature IDs
    feature_hours: Optional[dict[str, float]] = None  # {feature_id_str: base_hours_override}


# ── DUT Types ─────────────────────────────────────────────

class DutTypeBase(BaseModel):
    name: str
    category: Optional[str] = None
    complexity_multiplier: float = 1.0
    product_type: Optional[str] = None

class DutTypeCreate(DutTypeBase):
    pass

class DutTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    complexity_multiplier: Optional[float] = None
    product_type: Optional[str] = None

class DutTypeOut(DutTypeBase):
    id: int

    model_config = {"from_attributes": True}


# ── Test Profiles ─────────────────────────────────────────

class TestProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    effort_multiplier: float = 1.0
    product_type: Optional[str] = None
    is_active: bool = True

class TestProfileCreate(TestProfileBase):
    pass

class TestProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effort_multiplier: Optional[float] = None
    product_type: Optional[str] = None
    is_active: Optional[bool] = None

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
    estimation_id: Optional[int] = None

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
    team_id: Optional[int] = None
    linked_user_id: Optional[int] = None
    linked_user_name: Optional[str] = None

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
    product_type: Optional[str] = None

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
    product_type: Optional[str] = None

class RequestInboxReinit(BaseModel):
    """Confirmation payload for the destructive request-inbox reinitialize."""
    confirm: str

class EstimationReinit(BaseModel):
    """Confirmation payload for the destructive estimation reinitialize."""
    confirm: str

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


class PRDetailItem(BaseModel):
    pr_number: str
    link: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    complexity: str = "simple"
    status: str = "Open"
    test_available: bool = True

class TeamAllocationItem(BaseModel):
    team_member_id: int
    role: Optional[str] = None
    allocated_hours: float = 0
    team_member_name: Optional[str] = None

    model_config = {"from_attributes": True}


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
    formula: Optional[str] = None
    notes: Optional[str] = None
    feature_id: Optional[int] = None
    feature_name: Optional[str] = None

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
    expected_releases: int = 1
    risk_item_ids: list[int] = []
    document_type_ids: list[int] = []
    document_counts: dict[str, int] = {}  # {doc_type_id_str: count}

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
    pr_details: list[PRDetailItem] = []
    team_size: int = 1
    has_leader: bool = False
    start_date: Optional[date] = None
    expected_delivery: Optional[date] = None
    working_days: int = 20
    created_by: Optional[str] = None
    team_allocations: list[TeamAllocationItem] = []
    expected_releases: int = 1
    project_goals: Optional[str] = None
    target_customer: Optional[str] = None
    project_reference: Optional[str] = None
    team_id: Optional[int] = None
    risk_item_ids: list[int] = []
    document_type_ids: list[int] = []
    document_counts: dict[str, int] = {}  # {doc_type_id_str: count}
    task_assigned_testers: dict[str, int] = {}  # {task_name: tester_count}
    testing_start_date: Optional[str] = None
    product_type_filter: Optional[str] = None
    applied_presets: list[dict] = []  # [{id, name}] of presets applied in the wizard

class EstimationRiskOut(BaseModel):
    id: int
    risk_item_id: int
    risk_item_name: Optional[str] = None
    risk_item_category: Optional[str] = None
    risk_item_likelihood: Optional[str] = None
    risk_item_impact: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


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
    start_date: Optional[date] = None
    expected_delivery: Optional[date] = None
    total_tester_hours: float
    total_leader_hours: float
    pr_fix_hours: float = 0
    pr_no_test_hours: float = 0
    study_hours: float = 0
    release_extra_hours: float = 0
    documentation_hours: float = 0
    buffer_hours: float = 0
    grand_total_hours: float
    grand_total_days: float
    elapsed_hours: float = 0
    elapsed_days: float = 0
    elapsed_weeks: float = 0
    estimated_completion_date: Optional[date] = None
    feasibility_status: str
    status: str
    version: int = 1
    wizard_inputs_json: str = "{}"
    expected_releases: int = 1
    project_goals: Optional[str] = None
    target_customer: Optional[str] = None
    project_reference: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    request_number: Optional[str] = None
    tasks: list[EstimationTaskOut] = []
    team_allocations: list[TeamAllocationItem] = []
    risks: list[EstimationRiskOut] = []
    document_deliverables: list[dict] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_relationships(cls, data, handler):
        # When constructing from an ORM object, resolve relationships
        obj = handler(data)
        if obj.assigned_to_name is None and hasattr(data, "assigned_to") and data.assigned_to is not None:
            obj.assigned_to_name = data.assigned_to.display_name or data.assigned_to.username
        # Resolve team name
        if obj.team_name is None and hasattr(data, "team") and data.team is not None:
            obj.team_name = data.team.name
        # Resolve request number
        if obj.request_number is None and hasattr(data, "request") and data.request is not None:
            obj.request_number = data.request.request_number
        # Resolve team_member_name on each allocation
        if hasattr(data, "team_allocations"):
            for i, alloc in enumerate(data.team_allocations):
                if i < len(obj.team_allocations) and obj.team_allocations[i].team_member_name is None:
                    if hasattr(alloc, "team_member") and alloc.team_member is not None:
                        obj.team_allocations[i].team_member_name = alloc.team_member.name
        # Resolve risk item details
        if hasattr(data, "risks"):
            for i, er in enumerate(data.risks):
                if i < len(obj.risks) and obj.risks[i].risk_item_name is None:
                    if hasattr(er, "risk_item") and er.risk_item is not None:
                        obj.risks[i].risk_item_name = er.risk_item.name
                        obj.risks[i].risk_item_category = er.risk_item.category
                        obj.risks[i].risk_item_likelihood = er.risk_item.likelihood
                        obj.risks[i].risk_item_impact = er.risk_item.impact
        return obj

class EstimationUpdate(BaseModel):
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    expected_delivery: Optional[date] = None
    notes: Optional[str] = None
    project_goals: Optional[str] = None
    target_customer: Optional[str] = None
    project_reference: Optional[str] = None


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
    pr_details: list[PRDetailItem] = []
    team_size: int = 1
    has_leader: bool = False
    start_date: Optional[date] = None
    expected_delivery: Optional[date] = None
    working_days: int = 20
    team_allocations: list[TeamAllocationItem] = []
    expected_releases: int = 1
    project_goals: Optional[str] = None
    target_customer: Optional[str] = None
    project_reference: Optional[str] = None
    team_id: Optional[int] = None
    risk_item_ids: list[int] = []
    document_type_ids: list[int] = []
    document_counts: dict[str, int] = {}
    task_assigned_testers: dict[str, int] = {}  # {task_name: tester_count}
    testing_start_date: Optional[str] = None
    product_type_filter: Optional[str] = None
    applied_presets: list[dict] = []


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
    features_by_category: dict[str, int] = {}
    tasks_by_type: dict[str, int] = {}
    risks_by_category: dict[str, int] = {}
    risks_by_likelihood: dict[str, int] = {}


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
    pr_no_test_hours: float = 0
    study_hours: float
    release_extra_hours: float = 0
    documentation_hours: float = 0
    buffer_hours: float
    grand_total_hours: float
    grand_total_days: float
    feasibility_status: str
    capacity_hours: float
    utilization_pct: float
    elapsed_hours: float = 0
    elapsed_days: float = 0
    elapsed_weeks: float = 0
    risk_flags: list[str] = []
    risk_messages: list[str] = []


# ── Webhook Notifications ────────────────────────────────

class WebhookNotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str = ""
    source: str = "REDMINE"
    request_id: Optional[int] = None
    is_read: bool = False
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    unread_count: int


# ── Public Holidays ────────────────────────────────

class PublicHolidayCreate(BaseModel):
    date: date
    name: str
    country: str = ""
    is_recurring: bool = False

class PublicHolidayOut(BaseModel):
    id: int
    date: date
    name: str
    country: str = ""
    is_recurring: bool = False

    model_config = {"from_attributes": True}

class PublicHolidayUpdate(BaseModel):
    date: OptionalDate = None
    name: Optional[str] = None
    country: Optional[str] = None
    is_recurring: Optional[bool] = None


# ── Teams ────────────────────────────────────────────────

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class TeamOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    member_count: int = 0

    model_config = {"from_attributes": True}

class TeamMembersUpdate(BaseModel):
    member_ids: list[int] = []


# ── Task Presets ─────────────────────────────────────────

class TaskPresetCreate(BaseModel):
    name: str
    product_type: Optional[str] = None
    description: Optional[str] = None
    task_template_ids: list[int] = []

class TaskPresetUpdate(BaseModel):
    name: Optional[str] = None
    product_type: Optional[str] = None
    description: Optional[str] = None
    task_template_ids: Optional[list[int]] = None

class TaskPresetOut(BaseModel):
    id: int
    name: str
    product_type: Optional[str] = None
    description: Optional[str] = None
    task_template_ids: list[int] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Document Types ──────────────────────────────────────

class DocumentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "Report"
    base_effort_hours: float = 4.0
    task_template_id: Optional[int] = None

class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    base_effort_hours: Optional[float] = None
    is_active: Optional[bool] = None
    task_template_id: Optional[int] = None

class DocumentTypeOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: str
    base_effort_hours: float
    is_active: bool
    task_template_id: Optional[int] = None
    task_template_name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Risk Items ──────────────────────────────────────────

class RiskItemCreate(BaseModel):
    name: str
    category: str = "General"
    description: Optional[str] = None
    likelihood: str = "MEDIUM"
    impact: str = "MEDIUM"
    mitigation: Optional[str] = None

class RiskItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    likelihood: Optional[str] = None
    impact: Optional[str] = None
    mitigation: Optional[str] = None
    is_active: Optional[bool] = None

class RiskItemOut(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str] = None
    likelihood: str
    impact: str
    mitigation: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Backup / Restore ───────────────────────────────────

class BackupMetadata(BaseModel):
    version: str
    timestamp: str
    tables: dict[str, int]


class RestoreResult(BaseModel):
    status: str
    tables_restored: list[str]
    rows_restored: dict[str, int]
