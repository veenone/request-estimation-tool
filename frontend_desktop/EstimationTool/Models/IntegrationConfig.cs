using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class IntegrationConfig
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("system_name")] public string SystemName { get; set; } = "";
    [JsonPropertyName("base_url")] public string? BaseUrl { get; set; }
    [JsonPropertyName("username")] public string? Username { get; set; }
    [JsonPropertyName("additional_config_json")] public string AdditionalConfigJson { get; set; } = "{}";
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("last_sync_at")] public string? LastSyncAt { get; set; }
    [JsonPropertyName("has_api_key")] public bool HasApiKey { get; set; }
}
