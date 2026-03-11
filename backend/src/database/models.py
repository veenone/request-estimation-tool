"""SQLAlchemy 2.0 declarative models for the Test Effort Estimation Tool."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Many-to-many association: TaskTemplate ↔ Feature (with optional per-feature base_hours override)
class TaskTemplateFeature(Base):
    __tablename__ = "task_template_features"

    task_template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("task_templates.id", ondelete="CASCADE"), primary_key=True,
    )
    feature_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("features.id", ondelete="CASCADE"), primary_key=True,
    )
    base_hours_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    task_template: Mapped["TaskTemplate"] = relationship(viewonly=True)
    feature: Mapped["Feature"] = relationship(viewonly=True)


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    request_source: Mapped[str] = mapped_column(String, nullable=False, default="MANUAL")
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requester_name: Mapped[str] = mapped_column(String, nullable=False)
    requester_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    business_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="MEDIUM")
    status: Mapped[str] = mapped_column(String, default="NEW")
    requested_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    attachments_json: Mapped[str] = mapped_column(Text, default="[]")
    assigned_to_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    estimations: Mapped[list["Estimation"]] = relationship(back_populates="request")
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id])


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complexity_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    has_existing_tests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    study_effort_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Many-to-many: features linked to this template
    task_templates: Mapped[list["TaskTemplate"]] = relationship(
        secondary="task_template_features", back_populates="features", viewonly=True,
    )
    # Legacy one-to-many (kept for backward compat with feature_id FK column)
    owned_templates: Mapped[list["TaskTemplate"]] = relationship(
        back_populates="legacy_feature", cascade="all, delete-orphan",
        foreign_keys="TaskTemplate.feature_id",
    )


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    base_effort_hours: Mapped[float] = mapped_column(Float, nullable=False)
    scales_with_dut: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scales_with_profile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_parallelizable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Many-to-many features
    features: Mapped[list["Feature"]] = relationship(
        secondary="task_template_features", back_populates="task_templates",
    )
    # Legacy single-feature relationship (backward compat)
    legacy_feature: Mapped[Optional["Feature"]] = relationship(
        back_populates="owned_templates", foreign_keys=[feature_id],
    )


class DocumentType(Base):
    """Registry of document types for reporting/documentation tasks."""
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, default="Report")
    base_effort_hours: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    task_template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task_template: Mapped[Optional["TaskTemplate"]] = relationship()


class DutType(Base):
    __tablename__ = "dut_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complexity_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class TestProfile(Base):
    __tablename__ = "test_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effort_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HistoricalProject(Base):
    __tablename__ = "historical_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    project_type: Mapped[str] = mapped_column(String, nullable=False)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dut_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pr_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("estimations.id", ondelete="SET NULL"), nullable=True)


class Estimation(Base):
    __tablename__ = "estimations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("requests.id", ondelete="SET NULL"), nullable=True)
    estimation_number: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    project_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_project_ids: Mapped[str] = mapped_column(Text, default="[]")
    dut_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dut_profile_combinations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pr_fix_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_delivery: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_tester_hours: Mapped[float] = mapped_column(Float, default=0)
    total_leader_hours: Mapped[float] = mapped_column(Float, default=0)
    pr_fix_hours: Mapped[float] = mapped_column(Float, default=0)
    study_hours: Mapped[float] = mapped_column(Float, default=0)
    buffer_hours: Mapped[float] = mapped_column(Float, default=0)
    grand_total_hours: Mapped[float] = mapped_column(Float, default=0)
    grand_total_days: Mapped[float] = mapped_column(Float, default=0)
    feasibility_status: Mapped[str] = mapped_column(String, default="FEASIBLE")
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    wizard_inputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    expected_releases: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    release_extra_hours: Mapped[float] = mapped_column(Float, default=0)
    documentation_hours: Mapped[float] = mapped_column(Float, default=0)
    pr_no_test_hours: Mapped[float] = mapped_column(Float, default=0)
    project_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_customer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    request: Mapped[Optional["Request"]] = relationship(back_populates="estimations")
    tasks: Mapped[list["EstimationTask"]] = relationship(back_populates="estimation", cascade="all, delete-orphan")
    team_allocations: Mapped[list["EstimationTeamAllocation"]] = relationship(back_populates="estimation", cascade="all, delete-orphan")
    risks: Mapped[list["EstimationRisk"]] = relationship(back_populates="estimation", cascade="all, delete-orphan")
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])
    approver: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id])
    team: Mapped[Optional["Team"]] = relationship()


class EstimationTask(Base):
    __tablename__ = "estimation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimation_id: Mapped[int] = mapped_column(Integer, ForeignKey("estimations.id", ondelete="CASCADE"), nullable=False)
    task_template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True)
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    base_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    calculated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    assigned_testers: Mapped[int] = mapped_column(Integer, default=1)
    has_leader_support: Mapped[bool] = mapped_column(Boolean, default=False)
    leader_hours: Mapped[float] = mapped_column(Float, default=0)
    is_new_feature_study: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feature_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feature_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    estimation: Mapped["Estimation"] = relationship(back_populates="tasks")
    task_template: Mapped[Optional["TaskTemplate"]] = relationship()


class EstimationTeamAllocation(Base):
    __tablename__ = "estimation_team_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimation_id: Mapped[int] = mapped_column(Integer, ForeignKey("estimations.id", ondelete="CASCADE"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    allocated_hours: Mapped[float] = mapped_column(Float, default=0)

    estimation: Mapped["Estimation"] = relationship(back_populates="team_allocations")
    team_member: Mapped["TeamMember"] = relationship()


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    members: Mapped[list["TeamMember"]] = relationship(back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    available_hours_per_day: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    team: Mapped[Optional["Team"]] = relationship(back_populates="members")


class TaskPreset(Base):
    __tablename__ = "task_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_template_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RiskItem(Base):
    __tablename__ = "risk_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="General")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    likelihood: Mapped[str] = mapped_column(String, nullable=False, default="MEDIUM")
    impact: Mapped[str] = mapped_column(String, nullable=False, default="MEDIUM")
    mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EstimationRisk(Base):
    __tablename__ = "estimation_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimation_id: Mapped[int] = mapped_column(Integer, ForeignKey("estimations.id", ondelete="CASCADE"), nullable=False)
    risk_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_items.id", ondelete="CASCADE"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estimation: Mapped["Estimation"] = relationship(back_populates="risks")
    risk_item: Mapped["RiskItem"] = relationship()


class EstimationVersionSnapshot(Base):
    """Stores a snapshot of an estimation before it is revised."""
    __tablename__ = "estimation_version_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimation_id: Mapped[int] = mapped_column(Integer, ForeignKey("estimations.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    estimation: Mapped["Estimation"] = relationship()


class Configuration(Base):
    __tablename__ = "configuration"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WebhookNotification(Base):
    __tablename__ = "webhook_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="REDMINE")
    request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("requests.id", ondelete="SET NULL"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PublicHoliday(Base):
    __tablename__ = "public_holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class IntegrationConfig(Base):
    __tablename__ = "integration_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    additional_config_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)



# Auth models (User, UserSession, AuditLog) are defined in auth.models
# and share the same Base. They are registered with the ORM metadata
# automatically when auth.models is imported. Import them from
# ..auth.models wherever needed.
