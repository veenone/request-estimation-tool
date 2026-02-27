using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class TeamMember
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("role")] public string Role { get; set; } = "";
    [JsonPropertyName("available_hours_per_day")] public double AvailableHoursPerDay { get; set; } = 7.0;
    [JsonPropertyName("skills_json")] public string SkillsJson { get; set; } = "[]";
}
