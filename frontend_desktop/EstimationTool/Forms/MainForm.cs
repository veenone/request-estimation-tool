using EstimationTool.Forms.Panels;
using EstimationTool.Services;

namespace EstimationTool.Forms;

public class MainForm : Form
{
    private readonly BackendApiService _ipc;
    private readonly Panel _sidebar;
    private readonly Panel _contentArea;
    private readonly Label _statusLabel;
    private readonly Panel _statusBar;
    private Button? _activeButton;
    private UserControl? _currentPanel;

    private readonly record struct NavItem(string Name, string Label, string Icon);

    private static readonly NavItem[] NavItems =
    [
        new("Dashboard", "Dashboard", "\u2302"),
        new("Requests", "Request Inbox", "\u2709"),
        new("NewEstimation", "New Estimation", "\u2795"),
        new("Features", "Feature Catalog", "\u2605"),
        new("DutRegistry", "DUT Registry", "\u2699"),
        new("Profiles", "Test Profiles", "\u2263"),
        new("History", "History", "\u231A"),
        new("Team", "Team", "\u263A"),
        new("Integrations", "Integrations", "\u21C4"),
        new("Settings", "Settings", "\u2630"),
    ];

    public MainForm(BackendApiService ipcService)
    {
        _ipc = ipcService;

        Text = "Test Effort Estimation Tool";
        Size = new Size(1400, 900);
        MinimumSize = new Size(1100, 700);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = ThemeHelper.Background;
        ForeColor = ThemeHelper.Text;
        Font = new Font("Segoe UI", 9.5f);

        // Status bar
        _statusBar = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 28,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(8, 4, 8, 4),
        };
        _statusLabel = new Label
        {
            Dock = DockStyle.Left,
            AutoSize = true,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8.5f),
            Text = "Connecting...",
        };
        var reconnectBtn = new Button
        {
            Text = "Reconnect",
            Dock = DockStyle.Right,
            Width = 80,
            Height = 22,
            Visible = false,
            FlatStyle = FlatStyle.Flat,
            ForeColor = ThemeHelper.Text,
            BackColor = ThemeHelper.Accent,
            Font = new Font("Segoe UI", 7.5f),
            Tag = "reconnect",
        };
        reconnectBtn.FlatAppearance.BorderSize = 0;
        reconnectBtn.Click += async (s, ev) =>
        {
            reconnectBtn.Visible = false;
            try
            {
                await _ipc.EnsureConnectedAsync();
            }
            catch (Exception ex)
            {
                _statusLabel.Text = $"\u25CF Reconnect failed: {ex.Message}";
                reconnectBtn.Visible = true;
            }
        };

        _statusBar.Controls.Add(_statusLabel);
        _statusBar.Controls.Add(reconnectBtn);
        Controls.Add(_statusBar);

        // Sidebar
        _sidebar = new Panel
        {
            Dock = DockStyle.Left,
            Width = 220,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(0, 8, 0, 0),
        };

        // App title in sidebar
        var titleLabel = new Label
        {
            Text = "Estimation Tool",
            Dock = DockStyle.Top,
            Height = 50,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 13f),
            TextAlign = ContentAlignment.MiddleCenter,
            Padding = new Padding(0, 8, 0, 8),
        };
        _sidebar.Controls.Add(titleLabel);

        var navPanel = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(8, 4, 8, 4),
        };

        // Add nav buttons in reverse order (top dock stacking)
        for (int i = NavItems.Length - 1; i >= 0; i--)
        {
            var item = NavItems[i];
            var btn = new Button
            {
                Text = $"  {item.Icon}  {item.Label}",
                Dock = DockStyle.Top,
                Height = 42,
                Tag = item.Name,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(12, 0, 0, 0),
                Margin = new Padding(0, 2, 0, 2),
            };
            ThemeHelper.StyleSidebarButton(btn, false);
            btn.Click += NavButton_Click;
            navPanel.Controls.Add(btn);
        }

        _sidebar.Controls.Add(navPanel);
        Controls.Add(_sidebar);

        // Content area
        _contentArea = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(16),
        };
        Controls.Add(_contentArea);

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
        // Find reconnect button
        Button? reconnectBtn = null;
        foreach (Control c in _statusBar.Controls)
        {
            if (c is Button b && b.Tag as string == "reconnect")
            {
                reconnectBtn = b;
                break;
            }
        }

        switch (state)
        {
            case ConnectionState.Connected:
                _statusLabel.Text = "\u25CF Connected to backend";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityGreen;
                if (reconnectBtn != null) reconnectBtn.Visible = false;
                break;
            case ConnectionState.Connecting:
                _statusLabel.Text = "\u25CB Connecting...";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityAmber;
                if (reconnectBtn != null) reconnectBtn.Visible = false;
                break;
            case ConnectionState.Error:
                _statusLabel.Text = "\u25CF Connection error — backend is not running";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityRed;
                if (reconnectBtn != null) reconnectBtn.Visible = true;
                break;
            default:
                _statusLabel.Text = "\u25CB Disconnected";
                _statusLabel.ForeColor = ThemeHelper.TextSecondary;
                if (reconnectBtn != null) reconnectBtn.Visible = true;
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

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        _ipc.Dispose();
        base.OnFormClosing(e);
    }
}
