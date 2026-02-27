using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class DutType
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("category")] public string? Category { get; set; }
    [JsonPropertyName("complexity_multiplier")] public double ComplexityMultiplier { get; set; } = 1.0;
}
