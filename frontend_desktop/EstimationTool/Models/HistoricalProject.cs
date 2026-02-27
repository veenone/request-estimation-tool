using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class HistoricalProject
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("project_name")] public string ProjectName { get; set; } = "";
    [JsonPropertyName("project_type")] public string ProjectType { get; set; } = "";
    [JsonPropertyName("estimated_hours")] public double? EstimatedHours { get; set; }
    [JsonPropertyName("actual_hours")] public double? ActualHours { get; set; }
    [JsonPropertyName("dut_count")] public int? DutCount { get; set; }
    [JsonPropertyName("profile_count")] public int? ProfileCount { get; set; }
    [JsonPropertyName("pr_count")] public int? PrCount { get; set; }
    [JsonPropertyName("features_json")] public string FeaturesJson { get; set; } = "[]";
    [JsonPropertyName("completion_date")] public string? CompletionDate { get; set; }
    [JsonPropertyName("notes")] public string? Notes { get; set; }
}
