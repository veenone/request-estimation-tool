using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Manages external integration configurations for REDMINE, JIRA, and EMAIL.
/// Each system gets its own settings section with Save, Test Connection, and
/// Sync Now actions. All UI control creation lives in IntegrationsPanel.Designer.cs.
/// </summary>
public sealed partial class IntegrationsPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Private IPC response types
    // -------------------------------------------------------------------------

    private sealed class IntegrationsResponse
    {
        [JsonPropertyName("integrations")]
        public List<IntegrationConfig> Integrations { get; set; } = new();
    }

    private sealed class TestConnectionResult
    {
        [JsonPropertyName("success")]  public bool   Success { get; set; }
        [JsonPropertyName("message")]  public string Message { get; set; } = "";
    }

    private sealed class SyncResultResponse
    {
        [JsonPropertyName("status")]          public string       Status         { get; set; } = "";
        [JsonPropertyName("items_processed")] public int          ItemsProcessed { get; set; }
        [JsonPropertyName("items_created")]   public int          ItemsCreated   { get; set; }
        [JsonPropertyName("items_updated")]   public int          ItemsUpdated   { get; set; }
        [JsonPropertyName("items_failed")]    public int          ItemsFailed    { get; set; }
        [JsonPropertyName("errors")]          public List<string> Errors         { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Per-system control bag
    // -------------------------------------------------------------------------

    private sealed class SystemControls
    {
        public string SystemName { get; init; } = "";
        public CheckBox ChkEnabled  { get; init; } = null!;
        public TextBox  TxtBaseUrl  { get; init; } = null!;
        public TextBox  TxtApiKey   { get; init; } = null!;
        public TextBox  TxtUsername { get; init; } = null!;
        public TextBox  TxtConfig   { get; init; } = null!;
        public Label    LblResult   { get; init; } = null!;
        public Label    LblLastSync { get; init; } = null!;
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly List<SystemControls> _systemControls = new();

    private static readonly string[] KnownSystems = { "REDMINE", "JIRA", "EMAIL" };

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public IntegrationsPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        // InitializeComponent creates minimal VS-safe controls (header, spacers).
        InitializeComponent();

        // Build the 3 system cards AFTER InitializeComponent — this code lives
        // here (not in InitializeComponent) so VS Designer can't strip it out.
        BuildAllSystemCards();

        // Wire action buttons using the populated _systemControls list.
        foreach (var sc in _systemControls)
        {
            var captured = sc;

            var (save, test, sync) = FindButtonsForSystem(sc.SystemName);
            if (save is not null) save.Click += async (_, _) => await SaveIntegrationAsync(captured);
            if (test is not null) test.Click += async (_, _) => await TestConnectionAsync(captured);
            if (sync is not null) sync.Click += async (_, _) => await SyncNowAsync(captured);
        }

        HandleCreated += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Build all integration cards — called from constructor, NOT from
    // InitializeComponent, so VS Designer can never strip this code.
    // -------------------------------------------------------------------------

    private void BuildAllSystemCards()
    {
        // Apply styling that VS Designer would strip
        AutoScroll = true;
        BackColor = ThemeHelper.Background;
        Padding = new Padding(16);

        // Header label
        lblHeader.Text = "Integrations";
        lblHeader.Dock = DockStyle.Top;
        lblHeader.Height = 44;
        lblHeader.BackColor = Color.Transparent;
        lblHeader.ForeColor = ThemeHelper.Text;
        lblHeader.Font = new Font("Segoe UI Semibold", 18f, FontStyle.Bold);
        lblHeader.TextAlign = ContentAlignment.BottomLeft;
        lblHeader.Padding = new Padding(0, 0, 0, 8);

        // Spacers
        pnlSpacerAfterRedmine.Dock = DockStyle.Top;
        pnlSpacerAfterRedmine.Height = 16;
        pnlSpacerAfterRedmine.BackColor = Color.Transparent;

        pnlSpacerAfterJira.Dock = DockStyle.Top;
        pnlSpacerAfterJira.Height = 16;
        pnlSpacerAfterJira.BackColor = Color.Transparent;

        pnlBottomPadding.Dock = DockStyle.Top;
        pnlBottomPadding.Height = 24;
        pnlBottomPadding.BackColor = Color.Transparent;

        // Build the three system cards
        BuildSystemSection("REDMINE",
            out pnlCardRedmine, out lblTitleRedmine, out pnlDividerRedmine,
            out tblRedmine, out chkEnabledRedmine, out txtBaseUrlRedmine,
            out txtApiKeyRedmine, out txtUsernameRedmine, out txtConfigRedmine,
            out btnRowRedmine, out btnSaveRedmine, out btnTestRedmine, out btnSyncRedmine,
            out lblResultRedmine, out lblLastSyncRedmine);

        BuildSystemSection("JIRA",
            out pnlCardJira, out lblTitleJira, out pnlDividerJira,
            out tblJira, out chkEnabledJira, out txtBaseUrlJira,
            out txtApiKeyJira, out txtUsernameJira, out txtConfigJira,
            out btnRowJira, out btnSaveJira, out btnTestJira, out btnSyncJira,
            out lblResultJira, out lblLastSyncJira);

        BuildSystemSection("EMAIL",
            out pnlCardEmail, out lblTitleEmail, out pnlDividerEmail,
            out tblEmail, out chkEnabledEmail, out txtBaseUrlEmail,
            out txtApiKeyEmail, out txtUsernameEmail, out txtConfigEmail,
            out btnRowEmail, out btnSaveEmail, out btnTestEmail, out btnSyncEmail,
            out lblResultEmail, out lblLastSyncEmail);

        // Populate _systemControls for event wiring and data loading
        _systemControls.AddRange(new[]
        {
            new SystemControls
            {
                SystemName = "REDMINE", ChkEnabled = chkEnabledRedmine,
                TxtBaseUrl = txtBaseUrlRedmine, TxtApiKey = txtApiKeyRedmine,
                TxtUsername = txtUsernameRedmine, TxtConfig = txtConfigRedmine,
                LblResult = lblResultRedmine, LblLastSync = lblLastSyncRedmine,
            },
            new SystemControls
            {
                SystemName = "JIRA", ChkEnabled = chkEnabledJira,
                TxtBaseUrl = txtBaseUrlJira, TxtApiKey = txtApiKeyJira,
                TxtUsername = txtUsernameJira, TxtConfig = txtConfigJira,
                LblResult = lblResultJira, LblLastSync = lblLastSyncJira,
            },
            new SystemControls
            {
                SystemName = "EMAIL", ChkEnabled = chkEnabledEmail,
                TxtBaseUrl = txtBaseUrlEmail, TxtApiKey = txtApiKeyEmail,
                TxtUsername = txtUsernameEmail, TxtConfig = txtConfigEmail,
                LblResult = lblResultEmail, LblLastSync = lblLastSyncEmail,
            },
        });

        // Remove the VS-generated controls order and re-add in correct
        // reverse DockStyle.Top stacking order (last added = topmost).
        Controls.Clear();
        Controls.Add(pnlBottomPadding);
        Controls.Add(pnlCardEmail);
        Controls.Add(pnlSpacerAfterJira);
        Controls.Add(pnlCardJira);
        Controls.Add(pnlSpacerAfterRedmine);
        Controls.Add(pnlCardRedmine);
        Controls.Add(lblHeader);
    }

    /// <summary>
    /// Returns the (Save, Test, Sync) buttons for the given system name by
    /// matching the Designer field names that follow a consistent naming pattern.
    /// </summary>
    private (Button? save, Button? test, Button? sync) FindButtonsForSystem(string systemName) =>
        systemName.ToUpperInvariant() switch
        {
            "REDMINE" => (btnSaveRedmine, btnTestRedmine, btnSyncRedmine),
            "JIRA"    => (btnSaveJira,    btnTestJira,    btnSyncJira),
            "EMAIL"   => (btnSaveEmail,   btnTestEmail,   btnSyncEmail),
            _         => (null, null, null),
        };

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var response = await _ipc.SendCommandAsync<IntegrationsResponse>("get_integrations");
            if (IsDisposed) return;

            Action update = () =>
            {
                if (IsDisposed) return;
                foreach (var config in response.Integrations)
                {
                    var sc = FindSystemControls(config.SystemName);
                    if (sc is null) continue;
                    PopulateSystemControls(sc, config);
                }
            };

            if (InvokeRequired)
                BeginInvoke(update);
            else
                update();
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            Action showErr = () => ShowLoadError(ex.Message);
            if (InvokeRequired)
                BeginInvoke(showErr);
            else
                showErr();
        }
    }

    private static void PopulateSystemControls(SystemControls sc, IntegrationConfig config)
    {
        sc.ChkEnabled.Checked  = config.Enabled;
        sc.TxtBaseUrl.Text     = config.BaseUrl ?? "";
        sc.TxtUsername.Text    = config.Username ?? "";
        sc.TxtConfig.Text      = config.AdditionalConfigJson;

        // API key is stored encrypted server-side; show placeholder if key exists
        sc.TxtApiKey.Text = config.HasApiKey ? "••••••••" : "";

        sc.LblLastSync.Text = config.LastSyncAt is not null
            ? $"Last sync: {config.LastSyncAt}"
            : "Last sync: never";
    }

    // -------------------------------------------------------------------------
    // IPC action handlers
    // -------------------------------------------------------------------------

    private async Task SaveIntegrationAsync(SystemControls sc)
    {
        sc.LblResult.ForeColor = ThemeHelper.TextSecondary;
        sc.LblResult.Text = "Saving...";

        try
        {
            // If the user did not change the API key placeholder, send null so
            // the backend keeps the existing encrypted value.
            string? apiKey = sc.TxtApiKey.Text == "••••••••" ? null : sc.TxtApiKey.Text.Trim();
            if (string.IsNullOrEmpty(apiKey)) apiKey = null;

            await _ipc.SendCommandAsync<object>("update_integration", new
            {
                system_name            = sc.SystemName,
                base_url               = sc.TxtBaseUrl.Text.Trim(),
                api_key                = apiKey,
                username               = sc.TxtUsername.Text.Trim(),
                additional_config_json = sc.TxtConfig.Text.Trim(),
                enabled                = sc.ChkEnabled.Checked,
            });

            SetResult(sc.LblResult, success: true, "Settings saved.");
        }
        catch (Exception ex)
        {
            SetResult(sc.LblResult, success: false, $"Save failed: {ex.Message}");
        }
    }

    private async Task TestConnectionAsync(SystemControls sc)
    {
        sc.LblResult.ForeColor = ThemeHelper.TextSecondary;
        sc.LblResult.Text = "Testing connection...";

        try
        {
            var result = await _ipc.SendCommandAsync<TestConnectionResult>("test_integration", new
            {
                system_name = sc.SystemName,
            });

            SetResult(sc.LblResult, result.Success,
                result.Success ? "Connected!" : result.Message);
        }
        catch (Exception ex)
        {
            SetResult(sc.LblResult, success: false, $"Test failed: {ex.Message}");
        }
    }

    private async Task SyncNowAsync(SystemControls sc)
    {
        sc.LblResult.ForeColor = ThemeHelper.TextSecondary;
        sc.LblResult.Text = "Syncing...";

        try
        {
            var result = await _ipc.SendCommandAsync<SyncResultResponse>("trigger_sync", new
            {
                system_name = sc.SystemName,
            });

            var summary = $"Sync {result.Status} — " +
                          $"Processed: {result.ItemsProcessed}, " +
                          $"Created: {result.ItemsCreated}, " +
                          $"Updated: {result.ItemsUpdated}, " +
                          $"Failed: {result.ItemsFailed}";

            if (result.Errors.Count > 0)
                summary += $" | Errors: {string.Join("; ", result.Errors)}";

            bool success = result.Status?.ToUpperInvariant() is "OK" or "SUCCESS" or "PARTIAL"
                           && result.ItemsFailed == 0;
            SetResult(sc.LblResult, success, summary);

            // Refresh last sync label with current local time as a best approximation
            sc.LblLastSync.Text = $"Last sync: {DateTime.Now:yyyy-MM-dd HH:mm}";
        }
        catch (Exception ex)
        {
            SetResult(sc.LblResult, success: false, $"Sync failed: {ex.Message}");
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private SystemControls? FindSystemControls(string systemName) =>
        _systemControls.Find(sc =>
            string.Equals(sc.SystemName, systemName, StringComparison.OrdinalIgnoreCase));

    private static void SetResult(Label lbl, bool success, string message)
    {
        lbl.ForeColor = success ? ThemeHelper.FeasibilityGreen : ThemeHelper.FeasibilityRed;
        lbl.Text = message;
    }

    private void ShowLoadError(string message)
    {
        var lbl = new Label
        {
            Text      = $"Failed to load integrations: {message}",
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Top,
            AutoSize  = false,
            Height    = 32,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(4, 0, 0, 0),
            Font      = new Font("Segoe UI", 9.5f),
        };
        Controls.Add(lbl);
        lbl.BringToFront();
    }
}
