using System.Text.Json;
using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for viewing and editing global key-value configuration settings.
/// Loads all configuration from the backend and allows inline editing
/// with a Save button that persists each changed key individually.
/// </summary>
public class SettingsPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Known configuration keys with human-readable descriptions
    // -------------------------------------------------------------------------

    private static readonly (string Key, string Description)[] KnownKeys =
    [
        ("leader_effort_ratio",       "Leader Effort Ratio (fraction of tester hours)"),
        ("new_feature_study_hours",   "New Feature Study Hours (hours per new feature)"),
        ("working_hours_per_day",     "Working Hours Per Day"),
        ("buffer_percentage",         "Buffer Percentage (% added to grand total)"),
        ("estimation_number_prefix",  "Estimation Number Prefix (e.g. EST-)"),
        ("request_number_prefix",     "Request Number Prefix (e.g. REQ-)"),
    ];

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private readonly DataGridView _grid;
    private readonly Button _btnSave;
    private readonly Button _btnRefresh;
    private readonly Label _headerLabel;
    private readonly Label _subtitleLabel;

    // Tracks the original values to detect changes
    private Dictionary<string, string> _originalValues = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public SettingsPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // --- Header row ---
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 64,
            Padding = new Padding(0, 0, 0, 8),
        };

        _headerLabel = new Label
        {
            Text = "Settings",
            AutoSize = true,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);

        _subtitleLabel = new Label
        {
            Text = "Configure global defaults used in calculations and reports.",
            AutoSize = true,
            Location = new Point(0, 32),
        };
        ThemeHelper.StyleLabel(_subtitleLabel, isHeader: false);

        // --- Toolbar ---
        var toolbar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 40,
        };

        _btnRefresh = new Button
        {
            Text = "Refresh",
            Width = 90,
            Height = 32,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleButton(_btnRefresh, isPrimary: false);

        _btnSave = new Button
        {
            Text = "Save Changes",
            Width = 120,
            Height = 32,
            Location = new Point(96, 4),
        };
        ThemeHelper.StyleButton(_btnSave, isPrimary: true);

        toolbar.Controls.Add(_btnRefresh);
        toolbar.Controls.Add(_btnSave);

        headerPanel.Controls.Add(_subtitleLabel);
        headerPanel.Controls.Add(_headerLabel);

        // --- Backend URL section ---
        var backendPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            Padding = new Padding(0, 4, 0, 8),
        };

        var backendLabel = new Label
        {
            Text = "Backend URL:",
            AutoSize = true,
            Location = new Point(0, 10),
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 9f),
        };

        var txtBackendUrl = new TextBox
        {
            Text = _ipc.BaseUrl,
            Location = new Point(100, 7),
            Width = 300,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font = new Font("Segoe UI", 9f),
        };

        var btnTestConnection = new Button
        {
            Text = "Test Connection",
            Width = 120,
            Height = 28,
            Location = new Point(410, 6),
        };
        ThemeHelper.StyleButton(btnTestConnection, isPrimary: false);

        var btnSaveUrl = new Button
        {
            Text = "Save URL",
            Width = 90,
            Height = 28,
            Location = new Point(536, 6),
        };
        ThemeHelper.StyleButton(btnSaveUrl, isPrimary: true);

        btnTestConnection.Click += async (s, ev) =>
        {
            btnTestConnection.Enabled = false;
            try
            {
                var testService = new BackendApiService(txtBackendUrl.Text.Trim());
                await testService.EnsureConnectedAsync();
                testService.Dispose();
                MessageBox.Show("Connection successful!", "Test Connection",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Connection failed:\n{ex.Message}", "Test Connection",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                btnTestConnection.Enabled = true;
            }
        };

        btnSaveUrl.Click += (s, ev) =>
        {
            try
            {
                // Find appsettings.json by walking up from base directory
                var dir = AppDomain.CurrentDomain.BaseDirectory;
                string? settingsPath = null;
                for (int i = 0; i < 6; i++)
                {
                    var candidate = Path.Combine(dir, "appsettings.json");
                    if (File.Exists(candidate))
                    {
                        settingsPath = candidate;
                        break;
                    }
                    var parent = Directory.GetParent(dir);
                    if (parent == null) break;
                    dir = parent.FullName;
                }

                settingsPath ??= Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory, "appsettings.json");

                var json = File.Exists(settingsPath) ? File.ReadAllText(settingsPath) : "{}";
                using var doc = JsonDocument.Parse(json);
                var dict = new Dictionary<string, object>();
                foreach (var prop in doc.RootElement.EnumerateObject())
                {
                    dict[prop.Name] = prop.Value.ValueKind switch
                    {
                        JsonValueKind.String => prop.Value.GetString()!,
                        JsonValueKind.True => true,
                        JsonValueKind.False => false,
                        JsonValueKind.Number => prop.Value.GetDouble(),
                        _ => prop.Value.GetRawText(),
                    };
                }
                dict["BackendUrl"] = txtBackendUrl.Text.Trim();

                var options = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(settingsPath, JsonSerializer.Serialize(dict, options));

                MessageBox.Show(
                    "Backend URL saved. Restart the application for it to take effect.",
                    "Save URL", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to save URL:\n{ex.Message}", "Save Error",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        };

        backendPanel.Controls.Add(btnSaveUrl);
        backendPanel.Controls.Add(btnTestConnection);
        backendPanel.Controls.Add(txtBackendUrl);
        backendPanel.Controls.Add(backendLabel);

        // --- Grid ---
        _grid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = false,
            MultiSelect = false,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_grid);

        // Make only the Value column editable
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Key",
            HeaderText = "Setting Key",
            ReadOnly = true,
            FillWeight = 25,
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Description",
            HeaderText = "Description",
            ReadOnly = true,
            FillWeight = 45,
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Value",
            HeaderText = "Value",
            ReadOnly = false,
            FillWeight = 30,
        });

        // Style the editable cell distinctly so users know it is editable
        _grid.Columns["Value"].DefaultCellStyle.BackColor = ThemeHelper.Surface;
        _grid.Columns["Value"].DefaultCellStyle.ForeColor = ThemeHelper.Text;

        // -------------------------------------------------------------------------
        // Layout — add controls in bottom-to-top order for DockStyle stacking
        // -------------------------------------------------------------------------
        Controls.Add(_grid);
        Controls.Add(toolbar);
        Controls.Add(backendPanel);
        Controls.Add(headerPanel);

        // -------------------------------------------------------------------------
        // Wire events
        // -------------------------------------------------------------------------
        _btnRefresh.Click += async (s, e) => await LoadDataAsync();
        _btnSave.Click += BtnSave_Click;

        ThemeHelper.ApplyTheme(this);

        Load += async (s, e) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var config = await _ipc.SendCommandAsync<Dictionary<string, string>>("get_configuration");

            _originalValues = new Dictionary<string, string>(config, StringComparer.OrdinalIgnoreCase);

            _grid.Rows.Clear();

            // Show known keys first (in defined order), then any extra keys from backend
            var shownKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var (key, description) in KnownKeys)
            {
                config.TryGetValue(key, out var value);
                _grid.Rows.Add(key, description, value ?? "");
                shownKeys.Add(key);
            }

            foreach (var kvp in config)
            {
                if (!shownKeys.Contains(kvp.Key))
                    _grid.Rows.Add(kvp.Key, "", kvp.Value ?? "");
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load configuration:\n{ex.Message}",
                "Load Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Save
    // -------------------------------------------------------------------------

    private async void BtnSave_Click(object? sender, EventArgs e)
    {
        // Commit any in-progress cell edit
        _grid.EndEdit();

        var changed = new List<(string Key, string Value)>();

        foreach (DataGridViewRow row in _grid.Rows)
        {
            var key = row.Cells["Key"].Value?.ToString();
            var newValue = row.Cells["Value"].Value?.ToString() ?? "";

            if (string.IsNullOrWhiteSpace(key)) continue;

            _originalValues.TryGetValue(key, out var original);
            if (original != newValue)
                changed.Add((key, newValue));
        }

        if (changed.Count == 0)
        {
            MessageBox.Show(
                "No changes detected.",
                "Save Settings",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return;
        }

        try
        {
            _btnSave.Enabled = false;

            foreach (var (key, value) in changed)
            {
                await _ipc.SendCommandAsync<object>("set_configuration", new { key, value });
                _originalValues[key] = value;
            }

            MessageBox.Show(
                $"{changed.Count} setting(s) saved successfully.",
                "Save Settings",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to save settings:\n{ex.Message}",
                "Save Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
        finally
        {
            _btnSave.Enabled = true;
        }
    }
}
