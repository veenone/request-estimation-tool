using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step1ProjectType
{
    private System.ComponentModel.IContainer? components = null;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    // -------------------------------------------------------------------------
    // Designer-declared controls
    // -------------------------------------------------------------------------

    private Panel    _pnlScroll         = null!;
    private Label    _lblHeader         = null!;
    private Panel    _pnlDivider        = null!;

    // Request linkage section
    private Label    _lblReqSection     = null!;
    // _cmbRequest and _lblRequestInfo are declared in the main file (conditional visibility)

    // When no RequestId: field label above combo
    private Label    _lblReqField       = null!;

    // When RequestId is set: static info label (same as _lblRequestInfo, declared in main)

    // Project details section
    private Label    _lblDetailsSection = null!;
    private Label    _lblNameField      = null!;
    // _txtProjectName declared in main file
    private Label    _lblCreatedByField = null!;
    // _txtCreatedBy declared in main file

    // Project type section
    private Label    _lblTypeSection    = null!;

    // Card — NEW
    private Panel    _cardNew           = null!;
    // _rbNew declared in main file
    private Label    _lblNewDesc        = null!;

    // Card — EVOLUTION
    private Panel    _cardEvolution     = null!;
    // _rbEvolution declared in main file
    private Label    _lblEvolutionDesc  = null!;

    // Card — SUPPORT
    private Panel    _cardSupport       = null!;
    // _rbSupport declared in main file
    private Label    _lblSupportDesc    = null!;

    private void InitializeComponent()
    {
        components = new System.ComponentModel.Container();
        SuspendLayout();

        // ---- UserControl base -----------------------------------------------
        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        // ---- Scroll panel ---------------------------------------------------
        _pnlScroll = new Panel
        {
            Dock       = DockStyle.Fill,
            AutoScroll = true,
            BackColor  = ThemeHelper.Background,
        };

        // ---- Header ---------------------------------------------------------
        int y = 0;

        _lblHeader = new Label
        {
            Text      = "Step 1: Project Information",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 40;

        _pnlDivider = new Panel
        {
            BackColor = ThemeHelper.Border,
            Height    = 1,
            Left      = 0,
            Top       = y,
            Width     = 600,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        y += 16;

        // ---- Request linkage section ----------------------------------------
        _lblReqSection = new Label
        {
            Text      = "Linked Request (Optional)",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 24;

        // Static info label (shown when RequestId is set — _lblRequestInfo in main file)
        // Field label above combo (shown when no RequestId)
        _lblReqField = new Label
        {
            Text      = "Select Request",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
            Visible   = false, // visibility toggled in constructor
        };
        y += 20;

        // _cmbRequest and _lblRequestInfo are allocated in the main constructor
        // and added to _pnlScroll there; they are declared in the main file.
        // Reserve y-space for the combo + info row here (match BuildUI spacing):
        // combo row = 56, static info row = 28 — the constructor picks one branch.

        y += 56; // placeholder; actual layout managed in constructor
        y += 8;

        // ---- Project details section ----------------------------------------
        _lblDetailsSection = new Label
        {
            Text      = "Project Details",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 24;

        _lblNameField = new Label
        {
            Text      = "Project Name *",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 20;

        // _txtProjectName allocated in constructor; reserve y-space
        y += 36;

        _lblCreatedByField = new Label
        {
            Text      = "Created By",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 20;

        // _txtCreatedBy allocated in constructor; reserve y-space
        y += 44;

        // ---- Project type section -------------------------------------------
        _lblTypeSection = new Label
        {
            Text      = "Project Type *",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(0, y),
        };
        y += 24;

        // Card: NEW
        _rbNew = new RadioButton
        {
            Text      = "New Project",
            Tag       = "NEW",
            Font      = new Font("Segoe UI", 10f, FontStyle.Regular),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 10),
            AutoSize  = true,
        };
        _lblNewDesc = new Label
        {
            Text      = "Brand new feature set — all tasks start from scratch.",
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            Location  = new Point(32, 32),
            AutoSize  = true,
        };
        _cardNew = new Panel
        {
            Location  = new Point(0, y),
            Width     = 540,
            Height    = 64,
            BackColor = ThemeHelper.Surface,
            Cursor    = Cursors.Hand,
        };
        ThemeHelper.StylePanel(_cardNew);
        _cardNew.Controls.Add(_rbNew);
        _cardNew.Controls.Add(_lblNewDesc);
        y += 74;

        // Card: EVOLUTION
        _rbEvolution = new RadioButton
        {
            Text      = "Evolution",
            Tag       = "EVOLUTION",
            Font      = new Font("Segoe UI", 10f, FontStyle.Regular),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 10),
            AutoSize  = true,
        };
        _lblEvolutionDesc = new Label
        {
            Text      = "Enhancing an existing product — some existing tests apply.",
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            Location  = new Point(32, 32),
            AutoSize  = true,
        };
        _cardEvolution = new Panel
        {
            Location  = new Point(0, y),
            Width     = 540,
            Height    = 64,
            BackColor = ThemeHelper.Surface,
            Cursor    = Cursors.Hand,
        };
        ThemeHelper.StylePanel(_cardEvolution);
        _cardEvolution.Controls.Add(_rbEvolution);
        _cardEvolution.Controls.Add(_lblEvolutionDesc);
        y += 74;

        // Card: SUPPORT
        _rbSupport = new RadioButton
        {
            Text      = "Support",
            Tag       = "SUPPORT",
            Font      = new Font("Segoe UI", 10f, FontStyle.Regular),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(12, 10),
            AutoSize  = true,
        };
        _lblSupportDesc = new Label
        {
            Text      = "Maintenance, bug fixes, and regression testing on a known product.",
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            Location  = new Point(32, 32),
            AutoSize  = true,
        };
        _cardSupport = new Panel
        {
            Location  = new Point(0, y),
            Width     = 540,
            Height    = 64,
            BackColor = ThemeHelper.Surface,
            Cursor    = Cursors.Hand,
        };
        ThemeHelper.StylePanel(_cardSupport);
        _cardSupport.Controls.Add(_rbSupport);
        _cardSupport.Controls.Add(_lblSupportDesc);
        y += 74;

        // ---- Assemble scroll panel -----------------------------------------
        _pnlScroll.Controls.Add(_lblHeader);
        _pnlScroll.Controls.Add(_pnlDivider);
        _pnlScroll.Controls.Add(_lblReqSection);
        _pnlScroll.Controls.Add(_lblReqField);
        _pnlScroll.Controls.Add(_lblDetailsSection);
        _pnlScroll.Controls.Add(_lblNameField);
        _pnlScroll.Controls.Add(_lblCreatedByField);
        _pnlScroll.Controls.Add(_lblTypeSection);
        _pnlScroll.Controls.Add(_cardNew);
        _pnlScroll.Controls.Add(_cardEvolution);
        _pnlScroll.Controls.Add(_cardSupport);

        Controls.Add(_pnlScroll);

        ResumeLayout(false);
    }
}
