using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class IpcResponse<T>
{
    [JsonPropertyName("status")] public string Status { get; set; } = "";
    [JsonPropertyName("result")] public T? Result { get; set; }
    [JsonPropertyName("message")] public string? Message { get; set; }
}
