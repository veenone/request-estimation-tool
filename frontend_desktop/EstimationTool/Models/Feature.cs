using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class Feature
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("category")] public string? Category { get; set; }
    [JsonPropertyName("complexity_weight")] public double ComplexityWeight { get; set; } = 1.0;
    [JsonPropertyName("has_existing_tests")] public bool HasExistingTests { get; set; }
    [JsonPropertyName("description")] public string? Description { get; set; }
    [JsonPropertyName("task_templates")] public List<TaskTemplate> TaskTemplates { get; set; } = new();
}

public class TaskTemplate
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("feature_id")] public int? FeatureId { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("task_type")] public string TaskType { get; set; } = "";
    [JsonPropertyName("base_effort_hours")] public double BaseEffortHours { get; set; }
    [JsonPropertyName("scales_with_dut")] public bool ScalesWithDut { get; set; }
    [JsonPropertyName("scales_with_profile")] public bool ScalesWithProfile { get; set; }
    [JsonPropertyName("is_parallelizable")] public bool IsParallelizable { get; set; }
}
