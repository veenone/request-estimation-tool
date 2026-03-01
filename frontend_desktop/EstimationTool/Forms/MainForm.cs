using EstimationTool.Forms.Panels;
using EstimationTool.Services;

namespace EstimationTool.Forms;

public partial class MainForm : Form
{
    private readonly BackendApiService _ipc;
    private Button? _activeButton;
    private UserControl? _currentPanel;

    // -------------------------------------------------------------------------
    // Authentication state
    // -------------------------------------------------------------------------

    private string _authToken   = "";
    private string _userRole    = "";
    private string _displayName = "";

    // -------------------------------------------------------------------------
    // Extra sidebar controls
    // -------------------------------------------------------------------------

    private Button? _btnThemeToggle;
    private Button? _btnUsersNav;
    private Label?  _lblUserInfo;
    private Button? _btnLogout;

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

        // --- Add Users nav button (hidden until ADMIN login) ---
        _btnUsersNav = new Button
        {
            Text      = "  \u2617  Users",
            Dock      = DockStyle.Top,
            Height    = 38,
            Tag       = "Users",
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(16, 0, 0, 0),
            Margin    = new Padding(0, 1, 0, 1),
            Visible   = false,
        };
        ThemeHelper.StyleSidebarButton(_btnUsersNav, false);
        _btnUsersNav.Click += NavButton_Click;

        // Insert the Users button right after the ADMINISTRATION section buttons.
        // Since _navPanel uses DockStyle.Top stacking, adding to the end places it
        // at the bottom — which is fine, we want it after the other ADMINISTRATION items.
        // But we need to insert it at index 0 (bottom of the stack visually last).
        _navPanel.Controls.Add(_btnUsersNav);
        _navPanel.Controls.SetChildIndex(_btnUsersNav, 0);

        // --- Bottom dock panel: theme toggle, user info, logout ---
        var bottomPanel = new Panel
        {
            Dock      = DockStyle.Bottom,
            Height    = 110,
            BackColor = ThemeHelper.Sidebar,
            Padding   = new Padding(8, 4, 8, 8),
        };

        // Theme toggle button
        _btnThemeToggle = new Button
        {
            Text      = ThemeHelper.CurrentTheme == AppTheme.Dark ? "\u2600 Light Mode" : "\u263D Dark Mode",
            Dock      = DockStyle.Top,
            Height    = 32,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        ThemeHelper.StyleSidebarButton(_btnThemeToggle, false);
        _btnThemeToggle.Click += BtnThemeToggle_Click;

        // User info label
        _lblUserInfo = new Label
        {
            Text      = "",
            Dock      = DockStyle.Top,
            Height    = 28,
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        // Logout button
        _btnLogout = new Button
        {
            Text      = "\u2190 Logout",
            Dock      = DockStyle.Bottom,
            Height    = 32,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        ThemeHelper.StyleSidebarButton(_btnLogout, false);
        _btnLogout.ForeColor = ThemeHelper.FeasibilityRed;
        _btnLogout.Click += BtnLogout_Click;

        // Add to bottom panel (dock order: Bottom first, then Top items, Fill last)
        bottomPanel.Controls.Add(_lblUserInfo);
        bottomPanel.Controls.Add(_btnThemeToggle);
        bottomPanel.Controls.Add(_btnLogout);

        _sidebar.Controls.Add(bottomPanel);

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

        // Wire up theme changes
        ThemeHelper.ThemeChanged += OnThemeChanged;

        Load += MainForm_Load;
    }

    // -------------------------------------------------------------------------
    // Login flow
    // -------------------------------------------------------------------------

    private async void MainForm_Load(object? sender, EventArgs e)
    {
        try
        {
            _statusLabel.Text = "\u25CB Connecting to backend...";
            _statusLabel.ForeColor = ThemeHelper.FeasibilityAmber;

            await _ipc.EnsureConnectedAsync();
        }
        catch (Exception ex)
        {
            _statusLabel.Text = $"\u25CF Backend failed: {ex.Message}";
            _statusLabel.ForeColor = ThemeHelper.FeasibilityRed;

            var retry = MessageBox.Show(
                $"Failed to connect to backend:\n\n{ex.Message}\n\n" +
                "Make sure the backend server is running.\n\n" +
                "Retry to reconnect, or Cancel to continue with limited functionality.",
                "Connection Error",
                MessageBoxButtons.RetryCancel,
                MessageBoxIcon.Error);

            if (retry == DialogResult.Retry)
            {
                MainForm_Load(sender, e);
                return;
            }
            else
            {
                _statusLabel.Text = "Backend disconnected — some features unavailable";
                _statusLabel.ForeColor = ThemeHelper.FeasibilityAmber;
            }
        }

        // Show login dialog
        if (!ShowLoginDialog())
        {
            Application.Exit();
            return;
        }

        NavigateTo("Dashboard");
    }

    /// <summary>
    /// Shows the login dialog. Returns true on successful login, false if cancelled.
    /// </summary>
    private bool ShowLoginDialog()
    {
        using var loginForm = new LoginForm(_ipc);
        var result = loginForm.ShowDialog(this);

        if (result != DialogResult.OK)
            return false;

        // Store auth info
        _authToken   = loginForm.AuthToken;
        _userRole    = loginForm.UserRole;
        _displayName = loginForm.DisplayName;

        // Update sidebar UI
        UpdateUserInfo();

        return true;
    }

    /// <summary>
    /// Updates the sidebar to reflect the logged-in user.
    /// </summary>
    private void UpdateUserInfo()
    {
        if (_lblUserInfo is not null)
        {
            _lblUserInfo.Text = $"\u263A {_displayName} ({_userRole})";
        }

        // Show Users nav button only for ADMIN role
        if (_btnUsersNav is not null)
        {
            _btnUsersNav.Visible = _userRole.Equals("ADMIN", StringComparison.OrdinalIgnoreCase);
        }
    }

    // -------------------------------------------------------------------------
    // Theme toggle
    // -------------------------------------------------------------------------

    private void BtnThemeToggle_Click(object? sender, EventArgs e)
    {
        ThemeHelper.ToggleTheme();
    }

    private void OnThemeChanged(object? sender, AppTheme theme)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => OnThemeChanged(sender, theme));
            return;
        }

        // Update theme toggle button text
        if (_btnThemeToggle is not null)
        {
            _btnThemeToggle.Text = theme == AppTheme.Dark
                ? "\u2600 Light Mode"
                : "\u263D Dark Mode";
        }

        // Re-apply theme to entire form
        ReapplyTheme();
    }

    /// <summary>
    /// Re-applies all theme colors after a theme switch.
    /// </summary>
    private void ReapplyTheme()
    {
        SuspendLayout();

        // Form-level colors
        BackColor = ThemeHelper.Background;
        ForeColor = ThemeHelper.Text;

        // Status bar
        _statusBar.BackColor = ThemeHelper.Sidebar;
        _statusLabel.ForeColor = ThemeHelper.TextSecondary;
        _reconnectBtn.BackColor = ThemeHelper.Accent;
        _reconnectBtn.ForeColor = ThemeHelper.Text;

        // Sidebar
        _sidebar.BackColor = ThemeHelper.Sidebar;
        _titleLabel.ForeColor = ThemeHelper.Text;

        // Content area
        _contentArea.BackColor = ThemeHelper.Background;

        // Re-style all nav buttons and section headers
        foreach (Control c in _navPanel.Controls)
        {
            if (c is Button btn)
            {
                bool isActive = _activeButton != null && btn == _activeButton;
                ThemeHelper.StyleSidebarButton(btn, isActive);
            }
            else if (c is Label lbl)
            {
                lbl.ForeColor = ThemeHelper.TextSecondary;
            }
        }

        // Re-style bottom panel controls
        foreach (Control c in _sidebar.Controls)
        {
            if (c is Panel bottomPanel && c != _navPanel)
            {
                bottomPanel.BackColor = ThemeHelper.Sidebar;
                foreach (Control child in bottomPanel.Controls)
                {
                    if (child is Button btn)
                    {
                        ThemeHelper.StyleSidebarButton(btn, false);
                        // Restore logout red color
                        if (child == _btnLogout)
                            btn.ForeColor = ThemeHelper.FeasibilityRed;
                    }
                    else if (child is Label lbl)
                    {
                        lbl.ForeColor = ThemeHelper.TextSecondary;
                        lbl.BackColor = Color.Transparent;
                    }
                }
            }
        }

        // Re-apply theme to current panel if any
        if (_currentPanel is not null)
        {
            ThemeHelper.ApplyTheme(_currentPanel);
        }

        ResumeLayout(true);
        Refresh();
    }

    // -------------------------------------------------------------------------
    // Logout
    // -------------------------------------------------------------------------

    private void BtnLogout_Click(object? sender, EventArgs e)
    {
        var confirm = MessageBox.Show(
            "Are you sure you want to log out?",
            "Confirm Logout",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question);

        if (confirm != DialogResult.Yes) return;

        // Clear auth state
        _authToken   = "";
        _userRole    = "";
        _displayName = "";

        // Remove current panel
        if (_currentPanel is not null)
        {
            _contentArea.Controls.Remove(_currentPanel);
            _currentPanel.Dispose();
            _currentPanel = null;
        }

        // Hide Users nav
        if (_btnUsersNav is not null)
            _btnUsersNav.Visible = false;

        if (_lblUserInfo is not null)
            _lblUserInfo.Text = "";

        // Show login again
        if (!ShowLoginDialog())
        {
            Application.Exit();
            return;
        }

        NavigateTo("Dashboard");
    }

    // -------------------------------------------------------------------------
    // Connection status
    // -------------------------------------------------------------------------

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
                _statusLabel.Text = "\u25CF Connection error \u2014 backend is not running";
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

    // -------------------------------------------------------------------------
    // Navigation
    // -------------------------------------------------------------------------

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
            "Dashboard"        => new DashboardPanel(_ipc, this),
            "Requests"         => new RequestInboxPanel(_ipc, this),
            "NewEstimation"    => new WizardPanel(_ipc, this, context as int?),
            "Features"         => new FeatureCatalogPanel(_ipc),
            "DutRegistry"      => new DutRegistryPanel(_ipc),
            "Profiles"         => new ProfileManagerPanel(_ipc),
            "History"          => new HistoryPanel(_ipc),
            "Team"             => new TeamManagerPanel(_ipc),
            "Integrations"     => new IntegrationsPanel(_ipc),
            "Settings"         => new SettingsPanel(_ipc),
            "EstimationDetail" => new EstimationDetailPanel(_ipc, this, context as int? ?? 0),
            "Users"            => new UserManagementPanel(_ipc, _authToken),
            _                  => null,
        };
    }
}
