using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class CalculationResult
{
    [JsonPropertyName("tasks")] public List<CalculatedTask> Tasks { get; set; } = new();
    [JsonPropertyName("total_tester_hours")] public double TotalTesterHours { get; set; }
    [JsonPropertyName("total_leader_hours")] public double TotalLeaderHours { get; set; }
    [JsonPropertyName("pr_fix_hours")] public double PrFixHours { get; set; }
    [JsonPropertyName("study_hours")] public double StudyHours { get; set; }
    [JsonPropertyName("buffer_hours")] public double BufferHours { get; set; }
    [JsonPropertyName("grand_total_hours")] public double GrandTotalHours { get; set; }
    [JsonPropertyName("grand_total_days")] public double GrandTotalDays { get; set; }
    [JsonPropertyName("feasibility_status")] public string FeasibilityStatus { get; set; } = "";
    [JsonPropertyName("capacity_hours")] public double CapacityHours { get; set; }
    [JsonPropertyName("utilization_pct")] public double UtilizationPct { get; set; }
    [JsonPropertyName("risk_flags")] public List<string> RiskFlags { get; set; } = new();
    [JsonPropertyName("risk_messages")] public List<string> RiskMessages { get; set; } = new();
}

public class CalculatedTask
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("task_type")] public string TaskType { get; set; } = "";
    [JsonPropertyName("base_hours")] public double BaseHours { get; set; }
    [JsonPropertyName("dut_multiplier")] public double DutMultiplier { get; set; }
    [JsonPropertyName("profile_multiplier")] public double ProfileMultiplier { get; set; }
    [JsonPropertyName("complexity_weight")] public double ComplexityWeight { get; set; }
    [JsonPropertyName("calculated_hours")] public double CalculatedHours { get; set; }
    [JsonPropertyName("is_new_feature_study")] public bool IsNewFeatureStudy { get; set; }
}
