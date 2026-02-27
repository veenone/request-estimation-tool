using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class ReportResult
{
    [JsonPropertyName("filename")] public string Filename { get; set; } = "";
    [JsonPropertyName("mime_type")] public string MimeType { get; set; } = "";
    [JsonPropertyName("content_base64")] public string ContentBase64 { get; set; } = "";
    [JsonPropertyName("size_bytes")] public int SizeBytes { get; set; }
}
