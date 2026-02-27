using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Manages external integration configurations for REDMINE, JIRA, and EMAIL.
/// Each system gets its own settings section with Save, Test Connection, and
/// Sync Now actions. All UI is built programmatically — no designer file.
/// </summary>
public sealed class IntegrationsPanel : UserControl
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

        BackColor = ThemeHelper.Background;
        Dock = DockStyle.Fill;
        Padding = new Padding(0);
        AutoScroll = true;

        BuildLayout();

        HandleCreated += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Layout construction
    // -------------------------------------------------------------------------

    private void BuildLayout()
    {
        // Outer stack — everything docks Top inside an autoscroll UserControl
        var header = new Label
        {
            Text = "Integrations",
            Dock = DockStyle.Top,
            Height = 52,
            BackColor = ThemeHelper.Background,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
            Padding = new Padding(0, 0, 0, 8),
        };
        Controls.Add(header);

        // Build a section panel for each known integration system.
        // We add them in reverse so the first system ends up visually on top
        // after DockStyle.Top stacking.
        for (int i = KnownSystems.Length - 1; i >= 0; i--)
        {
            string system = KnownSystems[i];
            var section = BuildSystemSection(system, out var controls);
            _systemControls.Add(controls);
            Controls.Add(section);

            // Spacer between sections
            Controls.Add(new Panel
            {
                Dock = DockStyle.Top,
                Height = 12,
                BackColor = ThemeHelper.Background,
            });
        }

        // Bottom padding
        Controls.Add(new Panel { Dock = DockStyle.Top, Height = 16, BackColor = ThemeHelper.Background });
    }

    private Panel BuildSystemSection(string systemName, out SystemControls controls)
    {
        // Outer card panel
        var card = new Panel
        {
            Dock = DockStyle.Top,
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(16, 12, 16, 14),
            AutoSize = false,
            Height = 330,
        };
        card.Paint += PaintCardBorder;

        // System name header
        var titleLabel = new Label
        {
            Text = systemName,
            Dock = DockStyle.Top,
            Height = 28,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 11f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };
        card.Controls.Add(titleLabel);

        // Divider line below system name
        var divider = new Panel
        {
            Dock = DockStyle.Top,
            Height = 1,
            BackColor = ThemeHelper.Border,
            Margin = new Padding(0, 4, 0, 8),
        };
        card.Controls.Add(divider);

        // ---- Field rows using a 2-column TableLayoutPanel ----
        var fieldGrid = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = Color.Transparent,
            ColumnCount = 4,   // label | field | label | field
            RowCount = 3,
            Padding = new Padding(0, 6, 0, 6),
        };
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
        for (int r = 0; r < 3; r++)
            fieldGrid.RowStyles.Add(new RowStyle(SizeType.Absolute, 34f));

        // Row 0: Enabled | Base URL
        var chkEnabled = new CheckBox
        {
            Text = "Enabled",
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 9f),
            Dock = DockStyle.Fill,
            Margin = new Padding(0, 4, 0, 0),
        };
        fieldGrid.Controls.Add(chkEnabled, 0, 0);
        fieldGrid.SetColumnSpan(chkEnabled, 1);

        var txtBaseUrl = MakeTextBox();
        fieldGrid.Controls.Add(MakeCaptionPanel("Base URL", txtBaseUrl), 1, 0);
        fieldGrid.SetColumnSpan(fieldGrid.GetControlFromPosition(1, 0)!, 3); // Base URL spans cols 1–3

        // Row 1: API Key | Username
        var txtApiKey = MakeTextBox(passwordChar: true);
        var txtUsername = MakeTextBox();
        fieldGrid.Controls.Add(MakeCaptionPanel("API Key", txtApiKey), 0, 1);
        fieldGrid.SetColumnSpan(fieldGrid.GetControlFromPosition(0, 1)!, 2);
        fieldGrid.Controls.Add(MakeCaptionPanel("Username", txtUsername), 2, 1);
        fieldGrid.SetColumnSpan(fieldGrid.GetControlFromPosition(2, 1)!, 2);

        // Row 2: Additional Config (JSON) — spans all columns
        var txtConfig = MakeTextBox(multiline: true);
        txtConfig.Height = 64;
        fieldGrid.Controls.Add(MakeCaptionPanel("Additional Config (JSON)", txtConfig), 0, 2);
        fieldGrid.SetColumnSpan(fieldGrid.GetControlFromPosition(0, 2)!, 4);

        card.Controls.Add(fieldGrid);

        // ---- Action buttons row ----
        var btnRow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            Height = 40,
            BackColor = Color.Transparent,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0),
        };

        var btnSave = MakeActionButton("Save");
        var btnTest = MakeActionButton("Test Connection");
        var btnSync = MakeActionButton("Sync Now");
        ThemeHelper.StyleButton(btnSave, isPrimary: true);
        ThemeHelper.StyleButton(btnTest, isPrimary: false);
        ThemeHelper.StyleButton(btnSync, isPrimary: false);

        btnRow.Controls.Add(btnSave);
        btnRow.Controls.Add(btnTest);
        btnRow.Controls.Add(btnSync);
        card.Controls.Add(btnRow);

        // ---- Result label (shown after Test/Sync) ----
        var lblResult = new Label
        {
            Dock = DockStyle.Top,
            Height = 22,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Text = "",
            AutoEllipsis = true,
        };
        card.Controls.Add(lblResult);

        // ---- Last sync timestamp ----
        var lblLastSync = new Label
        {
            Dock = DockStyle.Top,
            Height = 20,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8f, FontStyle.Italic),
            TextAlign = ContentAlignment.MiddleLeft,
            Text = "Last sync: never",
        };
        card.Controls.Add(lblLastSync);

        // Bundle controls for later population and event wiring
        controls = new SystemControls
        {
            SystemName = systemName,
            ChkEnabled  = chkEnabled,
            TxtBaseUrl  = txtBaseUrl,
            TxtApiKey   = txtApiKey,
            TxtUsername = txtUsername,
            TxtConfig   = txtConfig,
            LblResult   = lblResult,
            LblLastSync = lblLastSync,
        };

        // Wire events with captured references
        var capturedControls = controls;
        btnSave.Click += async (_, _) => await SaveIntegrationAsync(capturedControls);
        btnTest.Click += async (_, _) => await TestConnectionAsync(capturedControls);
        btnSync.Click += async (_, _) => await SyncNowAsync(capturedControls);

        return card;
    }

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
                system_name           = sc.SystemName,
                base_url              = sc.TxtBaseUrl.Text.Trim(),
                api_key               = apiKey,
                username              = sc.TxtUsername.Text.Trim(),
                additional_config_json = sc.TxtConfig.Text.Trim(),
                enabled               = sc.ChkEnabled.Checked,
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

            bool success = result.Status?.ToUpperInvariant() == "OK" || result.ItemsFailed == 0;
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
            Text = $"Failed to load integrations: {message}",
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            AutoSize = false,
            Height = 32,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(4, 0, 0, 0),
            Font = new Font("Segoe UI", 9.5f),
        };
        Controls.Add(lbl);
        lbl.BringToFront();
    }

    // -------------------------------------------------------------------------
    // Control factory helpers
    // -------------------------------------------------------------------------

    private static TextBox MakeTextBox(bool passwordChar = false, bool multiline = false)
    {
        var txt = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = multiline,
            ScrollBars = multiline ? ScrollBars.Vertical : ScrollBars.None,
        };
        if (passwordChar) txt.PasswordChar = '*';
        ThemeHelper.StyleTextBox(txt);
        return txt;
    }

    /// <summary>
    /// Wraps a caption label and input control into a vertical pair panel.
    /// </summary>
    private static Panel MakeCaptionPanel(string caption, Control input)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 0, 8, 0),
        };

        var lbl = new Label
        {
            Text = caption,
            Dock = DockStyle.Top,
            Height = 16,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8f),
            TextAlign = ContentAlignment.BottomLeft,
            AutoSize = false,
        };

        input.Dock = DockStyle.Fill;
        panel.Controls.Add(input);
        panel.Controls.Add(lbl);
        return panel;
    }

    private static Button MakeActionButton(string text)
    {
        return new Button
        {
            Text = text,
            Height = 30,
            AutoSize = false,
            Width = text.Length > 10 ? 150 : 90,
            Margin = new Padding(0, 0, 8, 0),
        };
    }

    private static void PaintCardBorder(object? sender, PaintEventArgs e)
    {
        if (sender is not Panel p) return;
        using var pen = new Pen(ThemeHelper.Border, 1f);
        e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
    }
}
