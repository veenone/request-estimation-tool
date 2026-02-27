using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class TestProfile
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("description")] public string? Description { get; set; }
    [JsonPropertyName("effort_multiplier")] public double EffortMultiplier { get; set; } = 1.0;
}
