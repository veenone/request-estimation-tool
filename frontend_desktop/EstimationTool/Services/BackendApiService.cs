using System.Diagnostics;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace EstimationTool.Services;

/// <summary>
/// Represents the current connection state of the backend service.
/// </summary>
public enum ConnectionState
{
    Disconnected,
    Connecting,
    Connected,
    Error
}

/// <summary>
/// HTTP-based service that communicates with the FastAPI backend via REST.
/// Drop-in replacement for PythonIpcService — same public contract.
/// </summary>
public sealed class BackendApiService : IDisposable
{
    // -------------------------------------------------------------------------
    // JSON options — snake_case to match Python, case-insensitive reads
    // -------------------------------------------------------------------------

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        DictionaryKeyPolicy = null,
    };

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly HttpClient _http;
    private readonly string _baseUrl;

    private ConnectionState _connectionState = ConnectionState.Disconnected;
    private bool _disposed;

    // -------------------------------------------------------------------------
    // Events & Properties
    // -------------------------------------------------------------------------

    public event EventHandler<ConnectionState>? ConnectionStateChanged;

    public ConnectionState State
    {
        get => _connectionState;
        private set
        {
            if (_connectionState == value) return;
            _connectionState = value;
            ConnectionStateChanged?.Invoke(this, value);
        }
    }

    public bool IsBackendRunning => State == ConnectionState.Connected;

    public string BaseUrl => _baseUrl;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public BackendApiService(string baseUrl)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _http = new HttpClient
        {
            BaseAddress = new Uri(_baseUrl + "/"),
            Timeout = TimeSpan.FromSeconds(30),
        };
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /// <summary>
    /// Checks connectivity by hitting GET /api/dashboard/stats.
    /// </summary>
    public async Task EnsureConnectedAsync()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);

        if (State == ConnectionState.Connected)
            return;

        State = ConnectionState.Connecting;

        try
        {
            var url = $"{_baseUrl}/api/dashboard/stats";
            var resp = await _http.GetAsync(url).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
            State = ConnectionState.Connected;
        }
        catch (Exception ex)
        {
            State = ConnectionState.Error;
            throw new IpcException(
                $"Cannot reach backend at {_baseUrl}/api/dashboard/stats: {ex.Message}", ex);
        }
    }

    /// <summary>
    /// Routes an IPC-style command to the appropriate REST endpoint.
    /// </summary>
    public async Task<T> SendCommandAsync<T>(string command, object? payload = null)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);

        try
        {
            var result = await RouteCommandAsync<T>(command, payload).ConfigureAwait(false);
            // Mark connected on any successful call
            if (State != ConnectionState.Connected)
                State = ConnectionState.Connected;
            return result;
        }
        catch (HttpRequestException ex)
        {
            State = ConnectionState.Error;
            throw new IpcException($"HTTP error for command '{command}': {ex.Message}", command, ex);
        }
        catch (TaskCanceledException ex)
        {
            State = ConnectionState.Error;
            throw new IpcException($"Timeout for command '{command}'.", command, ex);
        }
        catch (IpcException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new IpcException($"Unexpected error for command '{command}': {ex.Message}", command, ex);
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _http.Dispose();
    }

    // -------------------------------------------------------------------------
    // Command routing
    // -------------------------------------------------------------------------

    private async Task<T> RouteCommandAsync<T>(string command, object? payload)
    {
        return command switch
        {
            // ── List / GET commands ─────────────────────────────
            "get_features"            => await GetWrapped<T>("/api/features", "features"),
            "get_task_templates"      => await GetWrapped<T>("/api/task-templates", "task_templates"),
            "get_dut_types"           => await GetWrapped<T>("/api/dut-types", "dut_types"),
            "get_profiles"            => await GetWrapped<T>("/api/profiles", "profiles"),
            "get_historical_projects" => await GetWrapped<T>("/api/historical-projects", "projects"),
            "get_team_members"        => await GetWrapped<T>("/api/team-members", "team_members"),
            "get_estimations"         => await GetWrapped<T>("/api/estimations", "estimations"),
            "get_integrations"        => await GetWrapped<T>("/api/integrations", "integrations"),
            "get_requests"            => await GetRequestsAsync<T>(payload),

            // ── Single-item GET ─────────────────────────────────
            "get_estimation"          => await GetByIdAsync<T>("/api/estimations", payload),
            "get_request"             => await GetByIdAsync<T>("/api/requests", payload),
            "get_request_detail"      => await GetRequestDetailAsync<T>(payload),
            "get_integration"         => await GetIntegrationAsync<T>(payload),
            "get_integration_status"  => await GetIntegrationStatusAsync<T>(payload),
            "get_dashboard_stats"     => await GetAsync<T>("/api/dashboard/stats"),

            // ── Configuration ───────────────────────────────────
            "get_configuration"       => await GetConfigurationAsync<T>(),
            "set_configuration"       => await SetConfigurationAsync<T>(payload),

            // ── Create / POST commands ──────────────────────────
            "create_feature"            => await PostAsync<T>("/api/features", payload),
            "create_task_template"      => await PostAsync<T>("/api/task-templates", payload),
            "create_dut_type"           => await PostAsync<T>("/api/dut-types", payload),
            "create_profile"            => await PostAsync<T>("/api/profiles", payload),
            "create_historical_project" => await PostAsync<T>("/api/historical-projects", payload),
            "create_team_member"        => await PostAsync<T>("/api/team-members", payload),
            "create_request"            => await PostAsync<T>("/api/requests", payload),
            "create_estimation"
                or "save_estimation"    => await PostAsync<T>("/api/estimations", payload),

            // ── Update / PUT commands ───────────────────────────
            "update_feature"       => await PutByIdAsync<T>("/api/features", payload),
            "update_task_template" => await PutByIdAsync<T>("/api/task-templates", payload),
            "update_dut_type"      => await PutByIdAsync<T>("/api/dut-types", payload),
            "update_profile"       => await PutByIdAsync<T>("/api/profiles", payload),
            "update_team_member"   => await PutByIdAsync<T>("/api/team-members", payload),
            "update_request"       => await PutByIdAsync<T>("/api/requests", payload),
            "update_estimation"    => await PutByIdAsync<T>("/api/estimations", payload),
            "update_integration"   => await UpdateIntegrationAsync<T>(payload),

            // ── Delete commands ─────────────────────────────────
            "delete_feature"       => await DeleteByIdAsync<T>("/api/features", payload),
            "delete_task_template" => await DeleteByIdAsync<T>("/api/task-templates", payload),
            "delete_dut_type"      => await DeleteByIdAsync<T>("/api/dut-types", payload),
            "delete_profile"       => await DeleteByIdAsync<T>("/api/profiles", payload),
            "delete_team_member"   => await DeleteByIdAsync<T>("/api/team-members", payload),
            "delete_request"       => await DeleteByIdAsync<T>("/api/requests", payload),
            "delete_estimation"    => await DeleteByIdAsync<T>("/api/estimations", payload),

            // ── Estimation workflow ─────────────────────────────
            "calculate_estimation"       => await PostAsync<T>("/api/estimations/calculate", payload),
            "recalculate_estimation"     => await RecalculateEstimationAsync<T>(payload),
            "update_estimation_status"   => await UpdateEstimationStatusAsync<T>(payload),
            "calibrate_estimation"       => await CalibrateEstimationAsync<T>(payload),

            // ── Reports ─────────────────────────────────────────
            "generate_report" => await GenerateReportAsync<T>(payload),

            // ── Integration actions ─────────────────────────────
            "test_integration" => await TestIntegrationAsync<T>(payload),
            "trigger_sync"     => await TriggerSyncAsync<T>(payload),

            // ── Send report email ───────────────────────────────
            "send_estimation_report" => await SendEstimationReportAsync<T>(payload),

            // ── Authentication & User management ─────────────────
            "login"       => await PostAsync<T>("/api/auth/login", payload),
            "get_users"   => await GetWrapped<T>("/api/users", "users"),
            "create_user" => await PostAsync<T>("/api/users", payload),
            "update_user" => await PutByIdAsync<T>("/api/users", payload),
            "delete_user" => await DeleteByIdAsync<T>("/api/users", payload),

            _ => throw new IpcException($"Unknown command: {command}", command),
        };
    }

    // -------------------------------------------------------------------------
    // HTTP helpers
    // -------------------------------------------------------------------------

    /// <summary>Builds an absolute URL from a relative API path.</summary>
    private string Url(string path) => $"{_baseUrl}{path}";

    private async Task<T> GetAsync<T>(string path)
    {
        var url = Url(path);
        var resp = await _http.GetAsync(url).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, path);
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    /// <summary>
    /// GET an array endpoint and wrap it into {"key": [...]} to match panel DTOs.
    /// </summary>
    private async Task<T> GetWrapped<T>(string path, string wrapperKey)
    {
        var url = Url(path);
        var resp = await _http.GetAsync(url).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, path);

        var json = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
        // Wrap the bare array: {"features": [...]}
        var wrapped = $"{{\"{wrapperKey}\": {json}}}";
        return JsonSerializer.Deserialize<T>(wrapped, JsonOptions)!;
    }

    private async Task<T> GetByIdAsync<T>(string basePath, object? payload)
    {
        int id = ExtractId(payload);
        var url = Url($"{basePath}/{id}");
        var resp = await _http.GetAsync(url).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"{basePath}/{id}");
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> PostAsync<T>(string path, object? payload)
    {
        var url = Url(path);
        var content = SerializePayload(payload);
        var resp = await _http.PostAsync(url, content).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, path);

        if (typeof(T) == typeof(object))
            return default!;

        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> PutByIdAsync<T>(string basePath, object? payload)
    {
        int id = ExtractId(payload);
        var url = Url($"{basePath}/{id}");
        var content = SerializePayload(payload);
        var resp = await _http.PutAsync(url, content).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"{basePath}/{id}");

        if (typeof(T) == typeof(object))
            return default!;

        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> DeleteByIdAsync<T>(string basePath, object? payload)
    {
        int id = ExtractId(payload);
        var url = Url($"{basePath}/{id}");
        var resp = await _http.DeleteAsync(url).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"{basePath}/{id}");
        return default!;
    }

    // -------------------------------------------------------------------------
    // Specialized command handlers
    // -------------------------------------------------------------------------

    private async Task<T> GetRequestsAsync<T>(object? payload)
    {
        string path = "/api/requests";
        var status = ExtractStringField(payload, "status");
        if (!string.IsNullOrEmpty(status))
            path += $"?status={Uri.EscapeDataString(status)}";

        return await GetWrapped<T>(path, "requests");
    }

    private async Task<T> GetRequestDetailAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        return await GetAsync<T>($"/api/requests/{id}/detail");
    }

    private async Task<T> GetIntegrationAsync<T>(object? payload)
    {
        string name = ExtractStringField(payload, "system_name")
            ?? throw new IpcException("system_name required", "get_integration");
        return await GetAsync<T>($"/api/integrations/{Uri.EscapeDataString(name)}");
    }

    private async Task<T> GetIntegrationStatusAsync<T>(object? payload)
    {
        string name = ExtractStringField(payload, "system_name")
            ?? throw new IpcException("system_name required", "get_integration_status");
        return await GetAsync<T>($"/api/integrations/{Uri.EscapeDataString(name)}/status");
    }

    private async Task<T> GetConfigurationAsync<T>()
    {
        // REST returns [{key, value, description}, ...] — panels expect Dictionary<string, string>
        var resp = await _http.GetAsync(Url("/api/configuration")).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, "/api/configuration");

        if (typeof(T) == typeof(Dictionary<string, string>))
        {
            var items = await resp.Content.ReadFromJsonAsync<List<ConfigEntry>>(JsonOptions)
                .ConfigureAwait(false);
            var dict = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in items ?? [])
                dict[item.Key] = item.Value;
            return (T)(object)dict;
        }

        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> SetConfigurationAsync<T>(object? payload)
    {
        string key = ExtractStringField(payload, "key")
            ?? throw new IpcException("key required", "set_configuration");
        string value = ExtractStringField(payload, "value") ?? "";

        var body = SerializePayload(new { value });
        var resp = await _http.PutAsync(
            Url($"/api/configuration/{Uri.EscapeDataString(key)}"), body).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/configuration/{key}");
        return default!;
    }

    private async Task<T> UpdateIntegrationAsync<T>(object? payload)
    {
        string name = ExtractStringField(payload, "system_name")
            ?? throw new IpcException("system_name required", "update_integration");
        var content = SerializePayload(payload);
        var resp = await _http.PutAsync(
            Url($"/api/integrations/{Uri.EscapeDataString(name)}"), content).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/integrations/{name}");
        return default!;
    }

    private async Task<T> RecalculateEstimationAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        var resp = await _http.PostAsync(Url($"/api/estimations/{id}/calculate"), null).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/estimations/{id}/calculate");
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> UpdateEstimationStatusAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        var content = SerializePayload(payload);
        var resp = await _http.PostAsync(Url($"/api/estimations/{id}/status"), content).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/estimations/{id}/status");
        return default!;
    }

    private async Task<T> CalibrateEstimationAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        var resp = await _http.PostAsync(Url($"/api/estimations/{id}/calibrate"), null).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/estimations/{id}/calibrate");
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> GenerateReportAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        string format = ExtractStringField(payload, "format") ?? "xlsx";

        var resp = await _http.GetAsync(Url($"/api/estimations/{id}/report/{format}")).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/estimations/{id}/report/{format}");

        var bytes = await resp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
        var contentDisposition = resp.Content.Headers.ContentDisposition?.FileName?.Trim('"')
            ?? $"report.{format}";
        var mimeType = resp.Content.Headers.ContentType?.MediaType ?? "application/octet-stream";

        // Build a ReportResult-shaped JSON and deserialize
        var reportJson = JsonSerializer.Serialize(new
        {
            filename = contentDisposition,
            mime_type = mimeType,
            content_base64 = Convert.ToBase64String(bytes),
            size_bytes = bytes.Length,
        }, JsonOptions);

        return JsonSerializer.Deserialize<T>(reportJson, JsonOptions)!;
    }

    private async Task<T> TestIntegrationAsync<T>(object? payload)
    {
        string name = ExtractStringField(payload, "system_name")
            ?? throw new IpcException("system_name required", "test_integration");
        var resp = await _http.PostAsync(
            Url($"/api/integrations/{Uri.EscapeDataString(name)}/test"), null).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/integrations/{name}/test");
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> TriggerSyncAsync<T>(object? payload)
    {
        string name = ExtractStringField(payload, "system_name")
            ?? throw new IpcException("system_name required", "trigger_sync");
        var resp = await _http.PostAsync(
            Url($"/api/integrations/{Uri.EscapeDataString(name)}/sync"), null).ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/integrations/{name}/sync");
        return (await resp.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false))!;
    }

    private async Task<T> SendEstimationReportAsync<T>(object? payload)
    {
        int id = ExtractId(payload);
        string email = ExtractStringField(payload, "to_email")
            ?? throw new IpcException("to_email required", "send_estimation_report");
        var resp = await _http.PostAsync(
            Url($"/api/estimations/{id}/send-report?to_email={Uri.EscapeDataString(email)}"), null)
            .ConfigureAwait(false);
        await EnsureSuccessOrThrow(resp, $"/api/estimations/{id}/send-report");
        return default!;
    }

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------

    private static StringContent SerializePayload(object? payload)
    {
        var json = payload is null ? "{}" : JsonSerializer.Serialize(payload, JsonOptions);
        return new StringContent(json, Encoding.UTF8, "application/json");
    }

    private static async Task EnsureSuccessOrThrow(HttpResponseMessage resp, string path)
    {
        if (resp.IsSuccessStatusCode)
            return;

        var body = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);

        // Try to extract FastAPI's {"detail": "..."} error message
        string message;
        try
        {
            using var doc = JsonDocument.Parse(body);
            message = doc.RootElement.TryGetProperty("detail", out var detail)
                ? detail.ToString()
                : body;
        }
        catch
        {
            message = body;
        }

        throw new IpcException(
            $"HTTP {(int)resp.StatusCode} from {path}: {message}",
            path, body);
    }

    /// <summary>
    /// Extracts "id" from an anonymous object payload via JSON round-trip.
    /// </summary>
    private static int ExtractId(object? payload)
    {
        if (payload is null)
            throw new IpcException("Payload with 'id' is required.");

        using var doc = JsonDocument.Parse(
            JsonSerializer.Serialize(payload, JsonOptions));

        if (doc.RootElement.TryGetProperty("id", out var idProp))
            return idProp.GetInt32();

        throw new IpcException("Payload must contain an 'id' field.");
    }

    private static string? ExtractStringField(object? payload, string fieldName)
    {
        if (payload is null) return null;

        using var doc = JsonDocument.Parse(
            JsonSerializer.Serialize(payload, JsonOptions));

        if (doc.RootElement.TryGetProperty(fieldName, out var prop))
            return prop.GetString();

        // Also try snake_case variant
        var snakeCase = JsonNamingPolicy.SnakeCaseLower.ConvertName(fieldName);
        if (snakeCase != fieldName && doc.RootElement.TryGetProperty(snakeCase, out prop))
            return prop.GetString();

        return null;
    }

    // -------------------------------------------------------------------------
    // Internal DTOs
    // -------------------------------------------------------------------------

    private sealed class ConfigEntry
    {
        [JsonPropertyName("key")] public string Key { get; set; } = "";
        [JsonPropertyName("value")] public string Value { get; set; } = "";
    }
}
