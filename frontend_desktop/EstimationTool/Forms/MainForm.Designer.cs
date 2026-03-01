using EstimationTool.Services;

namespace EstimationTool.Forms;

partial class MainForm
{
    private System.ComponentModel.IContainer components = null;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _ipc.Dispose();
            components?.Dispose();
        }
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        SuspendLayout();

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
        _reconnectBtn = new Button
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
        _reconnectBtn.FlatAppearance.BorderSize = 0;

        _statusBar.Controls.Add(_statusLabel);
        _statusBar.Controls.Add(_reconnectBtn);

        // Sidebar
        _sidebar = new Panel
        {
            Dock = DockStyle.Left,
            Width = 220,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(0, 8, 0, 0),
        };

        _titleLabel = new Label
        {
            Text = "Estimation Tool",
            Dock = DockStyle.Top,
            Height = 50,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 13f),
            TextAlign = ContentAlignment.MiddleCenter,
            Padding = new Padding(0, 8, 0, 8),
        };

        _navPanel = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(8, 4, 8, 4),
        };

        // Add order matters for WinForms docking: last added = lowest Z-order = laid out first.
        // _navPanel (Fill) must be added before _titleLabel (Top) so the title carves out
        // its 50 px first and the nav panel fills the remaining space without overlap.
        _sidebar.Controls.Add(_navPanel);
        _sidebar.Controls.Add(_titleLabel);

        // Content area
        _contentArea = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(16),
        };

        // Add order matters for DockStyle layout: last added = lowest Z-index = laid out first.
        // Fill must be added first (highest Z, laid out last) so edge-docked controls claim space first.
        Controls.Add(_contentArea);
        Controls.Add(_sidebar);
        Controls.Add(_statusBar);

        // Form properties
        Text = "Test Effort Estimation Tool";
        ClientSize = new Size(1400, 900);
        MinimumSize = new Size(1100, 700);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = ThemeHelper.Background;
        ForeColor = ThemeHelper.Text;
        Font = new Font("Segoe UI", 9.5f);

        ResumeLayout(false);
        PerformLayout();
    }

    private Panel _statusBar;
    private Label _statusLabel;
    private Button _reconnectBtn;
    private Panel _sidebar;
    private Label _titleLabel;
    private Panel _navPanel;
    private Panel _contentArea;
}
