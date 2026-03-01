using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class WizardPanel
{
    private System.ComponentModel.IContainer? components = null;

    // Controls created in InitializeComponent
    private Panel _progressPanel = null!;
    private Panel _contentPanel = null!;
    private Panel _buttonBar = null!;
    private Button _btnCancel = null!;
    private Button _btnBack = null!;
    private Button _btnNext = null!;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        SuspendLayout();

        // UserControl properties
        Dock = DockStyle.Fill;
        BackColor = ThemeHelper.Background;
        Padding = new Padding(0);

        // Progress bar panel (top)
        _progressPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 88,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(16, 0, 16, 0),
        };

        // Button bar (bottom)
        _buttonBar = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 66,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(16, 8, 16, 8),
        };

        _btnCancel = new Button
        {
            Text = "Cancel",
            Width = 90,
            Height = 40,
            Anchor = AnchorStyles.Left | AnchorStyles.Top,
        };
        _btnBack = new Button
        {
            Text = "< Back",
            Width = 90,
            Height = 40,
            Anchor = AnchorStyles.Right | AnchorStyles.Top,
        };
        _btnNext = new Button
        {
            Text = "Next >",
            Width = 110,
            Height = 40,
            Anchor = AnchorStyles.Right | AnchorStyles.Top,
        };

        ThemeHelper.StyleButton(_btnCancel, false);
        ThemeHelper.StyleButton(_btnBack,   false);
        ThemeHelper.StyleButton(_btnNext,   true);

        _btnCancel.Location = new Point(0, 13);
        _btnNext.Location   = new Point(_buttonBar.Width - 126, 13);
        _btnBack.Location   = new Point(_buttonBar.Width - 222, 13);

        _buttonBar.Controls.AddRange(new Control[] { _btnCancel, _btnBack, _btnNext });

        // Content area (fill)
        _contentPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(24, 16, 24, 16),
            AutoScroll = true,
        };

        // Add order matters for DockStyle layout: last added = lowest Z-index = laid out first.
        // Fill must be added first so edge-docked controls claim space first.
        Controls.Add(_contentPanel);
        Controls.Add(_buttonBar);
        Controls.Add(_progressPanel);

        ResumeLayout(false);
    }
}
