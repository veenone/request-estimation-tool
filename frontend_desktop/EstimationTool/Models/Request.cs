using System.Text.Json.Serialization;

namespace EstimationTool.Models;

public class Request
{
    [JsonPropertyName("id")] public int Id { get; set; }
    [JsonPropertyName("request_number")] public string RequestNumber { get; set; } = "";
    [JsonPropertyName("request_source")] public string RequestSource { get; set; } = "MANUAL";
    [JsonPropertyName("external_id")] public string? ExternalId { get; set; }
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("description")] public string? Description { get; set; }
    [JsonPropertyName("requester_name")] public string RequesterName { get; set; } = "";
    [JsonPropertyName("requester_email")] public string? RequesterEmail { get; set; }
    [JsonPropertyName("business_unit")] public string? BusinessUnit { get; set; }
    [JsonPropertyName("priority")] public string Priority { get; set; } = "MEDIUM";
    [JsonPropertyName("status")] public string Status { get; set; } = "NEW";
    [JsonPropertyName("requested_delivery_date")] public string? RequestedDeliveryDate { get; set; }
    [JsonPropertyName("received_date")] public string? ReceivedDate { get; set; }
    [JsonPropertyName("notes")] public string? Notes { get; set; }
    [JsonPropertyName("created_at")] public string? CreatedAt { get; set; }
}
