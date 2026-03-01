using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class DashboardStats
{
    [JsonPropertyName("total_requests")] public int TotalRequests { get; set; }
    [JsonPropertyName("requests_new")] public int RequestsNew { get; set; }
    [JsonPropertyName("requests_in_progress")] public int RequestsInProgress { get; set; }
    [JsonPropertyName("requests_completed")] public int RequestsCompleted { get; set; }
    [JsonPropertyName("total_estimations")] public int TotalEstimations { get; set; }
    [JsonPropertyName("estimations_draft")] public int EstimationsDraft { get; set; }
    [JsonPropertyName("estimations_final")] public int EstimationsFinal { get; set; }
    [JsonPropertyName("estimations_approved")] public int EstimationsApproved { get; set; }
    [JsonPropertyName("avg_grand_total_hours")] public double AvgGrandTotalHours { get; set; }
    [JsonPropertyName("recent_estimations")] public List<RecentEstimation> RecentEstimations { get; set; } = new();
    [JsonPropertyName("recent_requests")] public List<RecentRequest> RecentRequests { get; set; } = new();
}

public class RecentEstimation
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("estimation_number")] public string? EstimationNumber { get; set; }
    [JsonPropertyName("project_name")] public string ProjectName { get; set; } = "";
    [JsonPropertyName("grand_total_hours")] public double GrandTotalHours { get; set; }
    [JsonPropertyName("feasibility_status")] public string FeasibilityStatus { get; set; } = "";
    [JsonPropertyName("status")] public string Status { get; set; } = "";
    [JsonPropertyName("created_at")] public string? CreatedAt { get; set; }
    [JsonPropertyName("assigned_to_name")] public string? AssignedToName { get; set; }
}

public class RecentRequest
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("request_number")] public string RequestNumber { get; set; } = "";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("priority")] public string Priority { get; set; } = "";
    [JsonPropertyName("status")] public string Status { get; set; } = "";
    [JsonPropertyName("created_at")] public string? CreatedAt { get; set; }
    [JsonPropertyName("assigned_to_name")] public string? AssignedToName { get; set; }
}
