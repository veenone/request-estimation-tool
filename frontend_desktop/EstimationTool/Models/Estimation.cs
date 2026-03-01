using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class Estimation
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("request_id")] public int? RequestId { get; set; }
    [JsonPropertyName("request_source")] public string? RequestSource { get; set; }
    [JsonPropertyName("external_id")] public string? ExternalId { get; set; }
    [JsonPropertyName("estimation_number")] public string? EstimationNumber { get; set; }
    [JsonPropertyName("project_name")] public string ProjectName { get; set; } = "";
    [JsonPropertyName("project_type")] public string ProjectType { get; set; } = "";
    [JsonPropertyName("reference_project_ids")] public string ReferenceProjectIds { get; set; } = "[]";
    [JsonPropertyName("dut_count")] public int DutCount { get; set; }
    [JsonPropertyName("profile_count")] public int ProfileCount { get; set; }
    [JsonPropertyName("dut_profile_combinations")] public int DutProfileCombinations { get; set; }
    [JsonPropertyName("pr_fix_count")] public int PrFixCount { get; set; }
    [JsonPropertyName("expected_delivery")] public string? ExpectedDelivery { get; set; }
    [JsonPropertyName("total_tester_hours")] public double TotalTesterHours { get; set; }
    [JsonPropertyName("total_leader_hours")] public double TotalLeaderHours { get; set; }
    [JsonPropertyName("grand_total_hours")] public double GrandTotalHours { get; set; }
    [JsonPropertyName("grand_total_days")] public double GrandTotalDays { get; set; }
    [JsonPropertyName("feasibility_status")] public string FeasibilityStatus { get; set; } = "FEASIBLE";
    [JsonPropertyName("status")] public string Status { get; set; } = "DRAFT";
    [JsonPropertyName("created_at")] public string? CreatedAt { get; set; }
    [JsonPropertyName("created_by")] public string? CreatedBy { get; set; }
    [JsonPropertyName("approved_by")] public string? ApprovedBy { get; set; }
    [JsonPropertyName("approved_at")] public string? ApprovedAt { get; set; }
    [JsonPropertyName("assigned_to_id")] public int? AssignedToId { get; set; }
    [JsonPropertyName("assigned_to_name")] public string? AssignedToName { get; set; }
    [JsonPropertyName("tasks")] public List<EstimationTask> Tasks { get; set; } = new();
}

public class EstimationTask
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("task_template_id")] public int? TaskTemplateId { get; set; }
    [JsonPropertyName("task_name")] public string TaskName { get; set; } = "";
    [JsonPropertyName("task_type")] public string TaskType { get; set; } = "";
    [JsonPropertyName("base_hours")] public double BaseHours { get; set; }
    [JsonPropertyName("calculated_hours")] public double CalculatedHours { get; set; }
    [JsonPropertyName("assigned_testers")] public int AssignedTesters { get; set; } = 1;
    [JsonPropertyName("has_leader_support")] public bool HasLeaderSupport { get; set; }
    [JsonPropertyName("leader_hours")] public double LeaderHours { get; set; }
    [JsonPropertyName("is_new_feature_study")] public bool IsNewFeatureStudy { get; set; }
    [JsonPropertyName("notes")] public string? Notes { get; set; }
}
