using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step5PrFixes
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    private TableLayoutPanel _layout        = null!;

    // -------------------------------------------------------------------------
    // Header
    // -------------------------------------------------------------------------

    private Label _lblHeader = null!;

    // -------------------------------------------------------------------------
    // Form card
    // -------------------------------------------------------------------------

    private Panel _card     = null!;
    private Label _lblIntro = null!;

    // Simple PR row
    private Panel          _rowSimple   = null!;
    private Label          _lblSimple   = null!;
    private Label          _rateSimple  = null!;

    // Medium PR row
    private Panel          _rowMedium   = null!;
    private Label          _lblMedium   = null!;
    private Label          _rateMedium  = null!;

    // Complex PR row
    private Panel          _rowComplex  = null!;
    private Label          _lblComplex  = null!;
    private Label          _rateComplex = null!;

    // Total summary
    private Panel          _totalBorder = null!;

    // -------------------------------------------------------------------------
    // Field-level controls (also declared in main file — kept here for Designer)
    // -------------------------------------------------------------------------

    private NumericUpDown _nudSimple  = null!;
    private NumericUpDown _nudMedium  = null!;
    private NumericUpDown _nudComplex = null!;
    private Label         _lblTotal   = null!;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        components = new System.ComponentModel.Container();
        SuspendLayout();

        // ---- UserControl base ------------------------------------------------
        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        // ---- Root layout -----------------------------------------------------
        _layout = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 3,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        _layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        _layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 340));  // form card
        _layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // filler
        _layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- Header label ----------------------------------------------------
        _lblHeader = new Label
        {
            Text      = "Step 5: PR Fix Estimation",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _layout.Controls.Add(_lblHeader, 0, 0);

        // ---- Form card -------------------------------------------------------
        _card = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Width     = 460,
            Height    = 330,
            Anchor    = AnchorStyles.Top | AnchorStyles.Left,
        };
        ThemeHelper.StylePanel(_card);

        // Intro label
        _lblIntro = new Label
        {
            Text = "Estimate the number of PRs/defects expected by complexity.\r\n" +
                   "These add remediation effort to the total estimate.",
            Font      = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            AutoSize  = false,
            Width     = 420,
            Height    = 36,
            Location  = new Point(16, 16),
        };
        _card.Controls.Add(_lblIntro);

        // ---- Simple PR row (y = 64) ------------------------------------------
        _rowSimple = new Panel
        {
            Location  = new Point(16, 64),
            Width     = 420,
            Height    = 60,
            BackColor = ThemeHelper.Background,
        };
        ThemeHelper.StylePanel(_rowSimple);

        _lblSimple = new Label
        {
            Text      = "Simple PRs",
            Font      = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 8),
            AutoSize  = true,
        };

        _rateSimple = new Label
        {
            Text      = "2 hours each  — minor fixes, config changes",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(12, 28),
            AutoSize  = true,
        };

        _nudSimple = new NumericUpDown
        {
            Minimum     = 0,
            Maximum     = 100,
            Value       = 0,
            Width       = 80,
            Height      = 28,
            Location    = new Point(320, 16),
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };

        _rowSimple.Controls.AddRange(new Control[] { _lblSimple, _rateSimple, _nudSimple });
        _card.Controls.Add(_rowSimple);

        // ---- Medium PR row (y = 134) -----------------------------------------
        _rowMedium = new Panel
        {
            Location  = new Point(16, 134),
            Width     = 420,
            Height    = 60,
            BackColor = ThemeHelper.Background,
        };
        ThemeHelper.StylePanel(_rowMedium);

        _lblMedium = new Label
        {
            Text      = "Medium PRs",
            Font      = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 8),
            AutoSize  = true,
        };

        _rateMedium = new Label
        {
            Text      = "4 hours each  — moderate rework, logic changes",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(12, 28),
            AutoSize  = true,
        };

        _nudMedium = new NumericUpDown
        {
            Minimum     = 0,
            Maximum     = 100,
            Value       = 0,
            Width       = 80,
            Height      = 28,
            Location    = new Point(320, 16),
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };

        _rowMedium.Controls.AddRange(new Control[] { _lblMedium, _rateMedium, _nudMedium });
        _card.Controls.Add(_rowMedium);

        // ---- Complex PR row (y = 204) ----------------------------------------
        _rowComplex = new Panel
        {
            Location  = new Point(16, 204),
            Width     = 420,
            Height    = 60,
            BackColor = ThemeHelper.Background,
        };
        ThemeHelper.StylePanel(_rowComplex);

        _lblComplex = new Label
        {
            Text      = "Complex PRs",
            Font      = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 8),
            AutoSize  = true,
        };

        _rateComplex = new Label
        {
            Text      = "8 hours each  — significant analysis + rework",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(12, 28),
            AutoSize  = true,
        };

        _nudComplex = new NumericUpDown
        {
            Minimum     = 0,
            Maximum     = 100,
            Value       = 0,
            Width       = 80,
            Height      = 28,
            Location    = new Point(320, 16),
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };

        _rowComplex.Controls.AddRange(new Control[] { _lblComplex, _rateComplex, _nudComplex });
        _card.Controls.Add(_rowComplex);

        // ---- Total summary (y = 282) -----------------------------------------
        _totalBorder = new Panel
        {
            Location  = new Point(16, 282),
            Width     = 420,
            Height    = 42,
            BackColor = ThemeHelper.Sidebar,
        };

        _lblTotal = new Label
        {
            Text      = "Total PR effort:  0 h",
            Font      = new Font("Segoe UI Semibold", 11f, FontStyle.Bold),
            ForeColor = ThemeHelper.Accent,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        _totalBorder.Controls.Add(_lblTotal);
        _card.Controls.Add(_totalBorder);

        _layout.Controls.Add(_card, 0, 1);
        Controls.Add(_layout);

        ResumeLayout(false);
    }
}
