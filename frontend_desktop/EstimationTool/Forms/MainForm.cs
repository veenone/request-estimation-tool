using EstimationTool.Forms.Panels;
using EstimationTool.Services;

namespace EstimationTool.Forms;

public partial class MainForm : Form
{
    private readonly BackendApiService _ipc;
    private Button? _activeButton;
    private UserControl? _currentPanel;

    private readonly record struct NavItem(string Name, string Label, string Icon);

    /// <summary>
    /// Sidebar navigation grouped by scope. A null NavItem marks the start of
    /// a new section whose header text is stored in the Label field.
    /// </summary>
    private static readonly (string? SectionHeader, NavItem[] Items)[] NavSections =
    [
        ("OVERVIEW", [
            new("Dashboard",      "Dashboard",     "\u2302"),
            new("Requests",       "Request Inbox",  "\u2709"),
        ]),
        ("ESTIMATION", [
            new("NewEstimation",     "New Estimation",    "\u2795"),
            new("EstimationDetail",  "Estimation Detail", "\u2630"),
        ]),
        ("DATA MANAGEMENT", [
            new("Features",       "Feature Catalog", "\u2605"),
            new("DutRegistry",    "DUT Registry",    "\u2699"),
            new("Profiles",       "Test Profiles",   "\u2263"),
            new("History",        "Historical Projects", "\u231A"),
            new("Team",           "Team Members",    "\u263A"),
        ]),
        ("ADMINISTRATION", [
            new("Settings",       "Settings",       "\u2630"),
            new("Integrations",   "Integrations",   "\u21C4"),
        ]),
    ];

    public MainForm(BackendApiService ipcService)
    {
        _ipc = ipcService;

        InitializeComponent();

        // Wire up reconnect button
        _reconnectBtn.Click += async (s, ev) =>
        {
            _reconnectBtn.Visible = false;
            try
            {
                await _ipc.EnsureConnectedAsync();
            }
            catch (Exception ex)
            {
                _statusLabel.Text = $"\u25CF Reconnect failed: {ex.Message}";
                _reconnectBtn.Visible = true;
            }
        };

        // Build grouped sidebar: sections added in reverse order for DockStyle.Top stacking
        for (int s = NavSections.Length - 1; s >= 0; s--)
        {
            var (header, items) = NavSections[s];

            // Nav buttons within section (reverse order for top-dock stacking)
            for (int i = items.Length - 1; i >= 0; i--)
            {
                var item = items[i];
                var btn = new Button
                {
                    Text = $"  {item.Icon}  {item.Label}",
                    Dock = DockStyle.Top,
                    Height = 38,
                    Tag = item.Name,
                    TextAlign = ContentAlignment.MiddleLeft,
                    Padding = new Padding(16, 0, 0, 0),
                    Margin = new Padding(0, 1, 0, 1),
                };
                ThemeHelper.StyleSidebarButton(btn, false);
                btn.Click += NavButton_Click;
                _navPanel.Controls.Add(btn);
            }

            // Section header label (added last = appears on top due to dock stacking)
            if (header is not null)
            {
                var lbl = new Label
                {
                    Text = header,
                    Dock = DockStyle.Top,
                    Height = 28,
                    ForeColor = ThemeHelper.TextSecondary,
                    BackColor = Color.Transparent,
                    Font = new Font("Segoe UI Semibold", 7.5f, FontStyle.Bold),
                    TextAlign = ContentAlignment.BottomLeft,
                    Padding = new Padding(12, s == 0 ? 0 : 8, 0, 2),
                };
                _navPanel.Controls.Add(lbl);
            }
        }

        // Wire up IPC connection state
        _ipc.ConnectionStateChanged += (s, state) =>
        {
            if (InvokeRequired)
            {
                BeginInvoke(() => UpdateConnectionStatus(state));
            }
            else
            {
                UpdateConnectionStatus(state);
            }
        };

        Load += MainForm_Load;
    }

    private async void MainForm_Load(object? sender, EventArgs e)
    {
        try
        {
            _statusLabel.Text = "\u25CB Connecting to backend...";
            _statusLabel.ForeColor = ThemeHelper.FeasibilityAmber;

            await _ipc.EnsureConnectedAsync();
            NavigateTo("Dashboard");
        }
        catch (Exception ex)
        {
            _statusLabel.Text = $"\u25CF Backend failed: {ex.Message}";
            _statusLabel.ForeColor = ThemeHelper.FeasibilityRed;

            var retry = MessageBox.Show(
                $"Failed to connect to backend:\n\n{ex.Message}\n\n" +
                "Make sure the backend server is running.\n\n" +
                "Would you like to retry?",
                "Connection Error",
                MessageBoxButtons.RetryCancel,
                MessageBoxIcon.Error);

            if (retry == DialogResult.Retry)
            {
                MainForm_Load(sender, e);
            }
        }
    }

    private void UpdateConnectionStatus(ConnectionState state)
    {
        switch (state)
        {
            case ConnectionState.Connected:
                _statusLabel.Text = "\u25CF Connected to backend";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityGreen;
                _reconnectBtn.Visible = false;
                break;
            case ConnectionState.Connecting:
                _statusLabel.Text = "\u25CB Connecting...";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityAmber;
                _reconnectBtn.Visible = false;
                break;
            case ConnectionState.Error:
                _statusLabel.Text = "\u25CF Connection error — backend is not running";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityRed;
                _reconnectBtn.Visible = true;
                break;
            default:
                _statusLabel.Text = "\u25CB Disconnected";
                _statusLabel.ForeColor = ThemeHelper.TextSecondary;
                _reconnectBtn.Visible = true;
                break;
        }
    }

    private void NavButton_Click(object? sender, EventArgs e)
    {
        if (sender is Button btn && btn.Tag is string panelName)
        {
            NavigateTo(panelName);
        }
    }

    public void NavigateTo(string panelName, object? context = null)
    {
        // Update sidebar active state
        foreach (Control c in _sidebar.Controls)
        {
            if (c is Panel navPanel)
            {
                foreach (Control child in navPanel.Controls)
                {
                    if (child is Button btn)
                    {
                        bool isActive = (string)btn.Tag! == panelName;
                        ThemeHelper.StyleSidebarButton(btn, isActive);
                        if (isActive) _activeButton = btn;
                    }
                }
            }
        }

        // Dispose current panel
        if (_currentPanel != null)
        {
            _contentArea.Controls.Remove(_currentPanel);
            _currentPanel.Dispose();
        }

        // Create new panel
        _currentPanel = CreatePanel(panelName, context);
        if (_currentPanel != null)
        {
            _currentPanel.Dock = DockStyle.Fill;
            _contentArea.Controls.Add(_currentPanel);
        }
    }

    private UserControl? CreatePanel(string name, object? context)
    {
        return name switch
        {
            "Dashboard" => new DashboardPanel(_ipc, this),
            "Requests" => new RequestInboxPanel(_ipc, this),
            "NewEstimation" => new WizardPanel(_ipc, this, context as int?),
            "Features" => new FeatureCatalogPanel(_ipc),
            "DutRegistry" => new DutRegistryPanel(_ipc),
            "Profiles" => new ProfileManagerPanel(_ipc),
            "History" => new HistoryPanel(_ipc),
            "Team" => new TeamManagerPanel(_ipc),
            "Integrations" => new IntegrationsPanel(_ipc),
            "Settings" => new SettingsPanel(_ipc),
            "EstimationDetail" => new EstimationDetailPanel(_ipc, this, context as int? ?? 0),
            _ => null,
        };
    }
}
