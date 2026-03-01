using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step6DeliveryTeam
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    private TableLayoutPanel _layout = null!;

    // -------------------------------------------------------------------------
    // Header
    // -------------------------------------------------------------------------

    private Label _lblHeader = null!;

    // -------------------------------------------------------------------------
    // Form card
    // -------------------------------------------------------------------------

    private Panel _card = null!;

    // Delivery Timeline section
    private Label _lblSectionDelivery   = null!;
    private Panel _lineSectionDelivery  = null!;
    private Label _lblFieldDelivery     = null!;
    private Label _lblFieldWorkingDays  = null!;
    private Label _lblDaysHint          = null!;

    // Team Composition section
    private Label _lblSectionTeam      = null!;
    private Panel _lineSectionTeam     = null!;
    private Label _lblFieldTeamSize    = null!;

    // Capacity bar container
    private Panel _capPanel = null!;

    // -------------------------------------------------------------------------
    // Field-level controls (also declared in main file — kept here for Designer)
    // -------------------------------------------------------------------------

    private DateTimePicker _dtpDelivery    = null!;
    private CheckBox       _chkNoDeadline  = null!;
    private NumericUpDown  _nudWorkingDays = null!;
    private NumericUpDown  _nudTeamSize    = null!;
    private CheckBox       _chkHasLeader   = null!;
    private Label          _lblCapacity    = null!;
    private Panel          _pnlCapacityBar  = null!;
    private Panel          _pnlCapacityFill = null!;

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
        _layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 380));  // form card
        _layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // filler
        _layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- Header label ----------------------------------------------------
        _lblHeader = new Label
        {
            Text      = "Step 6: Delivery & Team",
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
            Width     = 520,
            Height    = 370,
            Anchor    = AnchorStyles.Top | AnchorStyles.Left,
        };
        ThemeHelper.StylePanel(_card);

        // y tracks the current vertical position within the card.
        // Delivery Timeline section header — y starts at 16
        // AddSectionLabel adds label at y, then line at y+26, advances y by 36.
        int y = 16;

        // ---- "Delivery Timeline" section label (y=16, line y=42, next y=52) --
        _lblSectionDelivery = new Label
        {
            Text      = "Delivery Timeline",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),   // 16
            AutoSize  = true,
        };
        _card.Controls.Add(_lblSectionDelivery);
        y += 26; // y = 42

        _lineSectionDelivery = new Panel
        {
            BackColor = ThemeHelper.Border,
            Location  = new Point(16, y),   // 42
            Size      = new Size(480, 1),
        };
        _card.Controls.Add(_lineSectionDelivery);
        y += 10; // y = 52

        // ---- "Expected Delivery Date" field label (y=52, next y=74) ----------
        _lblFieldDelivery = new Label
        {
            Text      = "Expected Delivery Date",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),   // 52
            AutoSize  = true,
        };
        _card.Controls.Add(_lblFieldDelivery);
        y += 22; // y = 74

        // ---- DateTimePicker + NoDeadline checkbox (y=74, next y=112) ---------
        _dtpDelivery = new DateTimePicker
        {
            Location                = new Point(16, y),  // 74
            Width                   = 200,
            Format                  = DateTimePickerFormat.Short,
            MinDate                 = DateTime.Today,
            CalendarForeColor       = ThemeHelper.Text,
            CalendarMonthBackground = ThemeHelper.Surface,
            ForeColor               = ThemeHelper.Text,
            Font                    = new Font("Segoe UI", 9f),
        };
        _card.Controls.Add(_dtpDelivery);

        _chkNoDeadline = new CheckBox
        {
            Text      = "No fixed deadline",
            Location  = new Point(220, y + 4),  // 78
            AutoSize  = true,
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 9f),
        };
        _card.Controls.Add(_chkNoDeadline);
        y += 38; // y = 112

        // ---- "Working Days Available" field label (y=112, next y=134) --------
        _lblFieldWorkingDays = new Label
        {
            Text      = "Working Days Available *",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),   // 112
            AutoSize  = true,
        };
        _card.Controls.Add(_lblFieldWorkingDays);
        y += 22; // y = 134

        // ---- Working days NumericUpDown (y=134, next y=172) ------------------
        _nudWorkingDays = new NumericUpDown
        {
            Location    = new Point(16, y),  // 134
            Width       = 100,
            Minimum     = 1,
            Maximum     = 365,
            Value       = 20,
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };
        _card.Controls.Add(_nudWorkingDays);
        y += 38; // y = 172

        // ---- Hint label (y=172, next y=200) ----------------------------------
        _lblDaysHint = new Label
        {
            Text      = "Tip: set the delivery date above to auto-calculate working days.",
            Location  = new Point(16, y),  // 172
            AutoSize  = true,
            Font      = new Font("Segoe UI", 8f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
        };
        _card.Controls.Add(_lblDaysHint);
        y += 28; // y = 200

        // ---- "Team Composition" section label (y=200, line y=226, next y=236) -
        _lblSectionTeam = new Label
        {
            Text      = "Team Composition",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),  // 200
            AutoSize  = true,
        };
        _card.Controls.Add(_lblSectionTeam);
        y += 26; // y = 226

        _lineSectionTeam = new Panel
        {
            BackColor = ThemeHelper.Border,
            Location  = new Point(16, y),  // 226
            Size      = new Size(480, 1),
        };
        _card.Controls.Add(_lineSectionTeam);
        y += 10; // y = 236

        // ---- "Number of Testers" field label (y=236, next y=258) ------------
        _lblFieldTeamSize = new Label
        {
            Text      = "Number of Testers *",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),  // 236
            AutoSize  = true,
        };
        _card.Controls.Add(_lblFieldTeamSize);
        y += 22; // y = 258

        // ---- Team size NumericUpDown (y=258, next y=296) ---------------------
        _nudTeamSize = new NumericUpDown
        {
            Location    = new Point(16, y),  // 258
            Width       = 100,
            Minimum     = 1,
            Maximum     = 50,
            Value       = 1,
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };
        _card.Controls.Add(_nudTeamSize);
        y += 38; // y = 296

        // ---- Has Leader checkbox (y=296, next y=328) -------------------------
        _chkHasLeader = new CheckBox
        {
            Text      = "Include Test Leader  (leader effort = 50% of total tester effort)",
            Location  = new Point(16, y),  // 296
            AutoSize  = true,
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 9f),
        };
        _card.Controls.Add(_chkHasLeader);
        y += 32; // y = 328

        // ---- Capacity info bar (y=336, after +8 padding) ---------------------
        y += 8; // y = 336

        _capPanel = new Panel
        {
            Location  = new Point(16, y),  // 336
            Width     = 480,
            Height    = 60,
            BackColor = ThemeHelper.Sidebar,
        };

        _lblCapacity = new Label
        {
            Dock      = DockStyle.Top,
            Height    = 28,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        _pnlCapacityFill = new Panel
        {
            Dock      = DockStyle.Left,
            BackColor = ThemeHelper.Accent,
            Width     = 0,
        };

        _pnlCapacityBar = new Panel
        {
            Dock      = DockStyle.Bottom,
            Height    = 6,
            BackColor = ThemeHelper.Border,
        };
        _pnlCapacityBar.Controls.Add(_pnlCapacityFill);

        _capPanel.Controls.Add(_pnlCapacityBar);
        _capPanel.Controls.Add(_lblCapacity);
        _card.Controls.Add(_capPanel);

        // Add card to layout
        _layout.Controls.Add(_card, 0, 1);
        Controls.Add(_layout);

        ResumeLayout(false);
    }
}
