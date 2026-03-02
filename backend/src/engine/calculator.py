"""Core estimation calculation engine.

Implements the formulas from SPEC §4.1-4.2:
  Task_Effort = Base_Hours × DUT_Multiplier × Profile_Multiplier × Complexity_Weight
  Grand Total = Tester + Leader + PR_Fix + Study + Buffer
"""

from dataclasses import dataclass, field
from enum import Enum


class ProjectType(str, Enum):
    NEW = "NEW"
    EVOLUTION = "EVOLUTION"
    SUPPORT = "SUPPORT"


class TaskType(str, Enum):
    SETUP = "SETUP"
    EXECUTION = "EXECUTION"
    ANALYSIS = "ANALYSIS"
    REPORTING = "REPORTING"
    STUDY = "STUDY"


class PRComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


PR_COMPLEXITY_HOURS: dict[str, float] = {
    "simple": 2.0,
    "medium": 4.0,
    "complex": 8.0,
}


@dataclass
class TaskInput:
    """Input data for a single task calculation."""

    name: str
    task_type: str
    base_effort_hours: float
    scales_with_dut: bool = False
    scales_with_profile: bool = False
    complexity_weight: float = 1.0
    is_new_feature_study: bool = False
    template_id: int | None = None


@dataclass
class TaskResult:
    """Result of calculating a single task's effort."""

    name: str
    task_type: str
    base_hours: float
    dut_multiplier: int
    profile_multiplier: int
    complexity_weight: float
    calculated_hours: float
    is_new_feature_study: bool = False
    template_id: int | None = None


@dataclass
class PRFixInput:
    """PR fix counts by complexity."""

    simple: int = 0
    medium: int = 0
    complex: int = 0


@dataclass
class EstimationInput:
    """All inputs needed to compute an estimation."""

    project_type: str
    tasks: list[TaskInput]
    dut_count: int
    profile_count: int
    pr_fixes: PRFixInput = field(default_factory=PRFixInput)
    new_feature_count: int = 0
    team_size: int = 1
    has_leader: bool = False
    working_days: int = 20
    # Configurable parameters (defaults from SPEC)
    leader_effort_ratio: float = 0.5
    new_feature_study_hours: float = 16.0
    working_hours_per_day: float = 7.0
    buffer_percentage: float = 10.0
    pr_scales_with_profile: bool = False


@dataclass
class EstimationResult:
    """Complete estimation calculation result."""

    tasks: list[TaskResult]
    total_tester_hours: float
    total_leader_hours: float
    pr_fix_hours: float
    study_hours: float
    subtotal_hours: float
    buffer_hours: float
    grand_total_hours: float
    grand_total_days: float
    capacity_hours: float
    utilization_pct: float
    feasibility_status: str


def calculate_task_effort(
    task: TaskInput,
    dut_count: int,
    profile_count: int,
) -> TaskResult:
    """Calculate effort for a single task.

    Formula: base_hours × dut_multiplier × profile_multiplier × complexity_weight
    """
    dut_multiplier = dut_count if task.scales_with_dut else 1
    profile_multiplier = profile_count if task.scales_with_profile else 1

    calculated = (
        task.base_effort_hours
        * dut_multiplier
        * profile_multiplier
        * task.complexity_weight
    )

    return TaskResult(
        name=task.name,
        task_type=task.task_type,
        base_hours=task.base_effort_hours,
        dut_multiplier=dut_multiplier,
        profile_multiplier=profile_multiplier,
        complexity_weight=task.complexity_weight,
        calculated_hours=calculated,
        is_new_feature_study=task.is_new_feature_study,
        template_id=task.template_id,
    )


def calculate_pr_fix_effort(
    pr_fixes: PRFixInput,
    dut_count: int = 1,
    profile_count: int = 1,
    pr_scales_with_profile: bool = False,
) -> float:
    """Calculate total PR fix validation effort.

    Each PR is validated per DUT (scales_with_dut = true per SPEC §9.2).
    Optionally scales with profile count if pr_scales_with_profile is enabled.
    """
    total = (
        pr_fixes.simple * PR_COMPLEXITY_HOURS["simple"]
        + pr_fixes.medium * PR_COMPLEXITY_HOURS["medium"]
        + pr_fixes.complex * PR_COMPLEXITY_HOURS["complex"]
    )
    profile_factor = profile_count if pr_scales_with_profile else 1
    return total * dut_count * profile_factor


def calculate_estimation(inputs: EstimationInput) -> EstimationResult:
    """Run the full estimation calculation.

    Aggregation per SPEC §4.2:
      total_tester  = Σ(task efforts)
      leader_effort = total_tester × leader_effort_ratio
      pr_fix_effort = Σ(pr_count × hours_per_complexity) × dut_count
      study_effort  = new_feature_count × new_feature_study_hours
      buffer        = subtotal × buffer_percentage / 100
      grand_total   = tester + leader + pr_fix + study + buffer
    """
    # Calculate each task
    task_results = [
        calculate_task_effort(task, inputs.dut_count, inputs.profile_count)
        for task in inputs.tasks
    ]

    # Aggregate tester effort
    total_tester = sum(t.calculated_hours for t in task_results)

    # Test leader effort
    total_leader = total_tester * inputs.leader_effort_ratio if inputs.has_leader else 0.0

    # PR fix effort
    pr_fix_hours = calculate_pr_fix_effort(
        inputs.pr_fixes,
        inputs.dut_count,
        inputs.profile_count,
        inputs.pr_scales_with_profile,
    )

    # New feature study effort (already included in tasks if study tasks are provided,
    # but this is the separate line item from SPEC §4.2 for features flagged as new)
    study_hours = inputs.new_feature_count * inputs.new_feature_study_hours

    # Subtotal before buffer
    subtotal = total_tester + total_leader + pr_fix_hours + study_hours

    # Buffer
    buffer = subtotal * inputs.buffer_percentage / 100.0

    # Grand total
    grand_total = subtotal + buffer
    grand_total_days = grand_total / inputs.working_hours_per_day

    # Capacity and feasibility
    team_size = inputs.team_size + (1 if inputs.has_leader else 0)
    capacity = inputs.working_days * team_size * inputs.working_hours_per_day
    utilization = (grand_total / capacity * 100.0) if capacity > 0 else 999.0

    if grand_total <= capacity * 0.8:
        feasibility = "FEASIBLE"
    elif grand_total <= capacity:
        feasibility = "AT_RISK"
    else:
        feasibility = "NOT_FEASIBLE"

    return EstimationResult(
        tasks=task_results,
        total_tester_hours=total_tester,
        total_leader_hours=total_leader,
        pr_fix_hours=pr_fix_hours,
        study_hours=study_hours,
        subtotal_hours=subtotal,
        buffer_hours=buffer,
        grand_total_hours=grand_total,
        grand_total_days=round(grand_total_days, 1),
        capacity_hours=capacity,
        utilization_pct=round(utilization, 1),
        feasibility_status=feasibility,
    )
