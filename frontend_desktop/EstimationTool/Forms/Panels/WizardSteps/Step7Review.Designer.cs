using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step7Review
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

    // Outer layout
    private TableLayoutPanel _tblOuter     = null!;

    // Row 0: Header
    private Label _lblHeader               = null!;

    // Row 1: Calculate row
    private Panel _pnlCalcRow              = null!;
    // _btnCalculate declared in main file
    private Panel _pnlLoading              = null!;
    private Label _lblLoadingText          = null!;

    // Row 2: Results panel
    private Panel _pnlResults              = null!;

    // Results — summary cards row
    private TableLayoutPanel _tblCards     = null!;

    // Wrapper panels for each card
    private Panel _wrapTester              = null!;
    private Panel _wrapLeader              = null!;
    private Panel _wrapPr                  = null!;
    private Panel _wrapStudy               = null!;
    private Panel _wrapBuffer              = null!;
    private Panel _wrapTotal               = null!;
    private Panel _wrapDays                = null!;

    // Metric card panels (returned by ThemeHelper.CreateMetricCard)
    private Panel _cardTester              = null!;
    private Panel _cardLeader              = null!;
    private Panel _cardPr                  = null!;
    private Panel _cardStudy               = null!;
    private Panel _cardBuffer              = null!;
    private Panel _cardTotal               = null!;
    private Panel _cardDays                = null!;

    // Summary card value labels (Controls[0] of each card — declared in main file)
    // _lblTesterHours, _lblLeaderHours, _lblPrHours, _lblStudyHours,
    // _lblBufferHours, _lblGrandTotal, _lblGrandDays

    // Results — feasibility + utilisation row
    private Panel _pnlFeasRow              = null!;
    // _pnlFeasBadge, _lblFeasText, _lblUtilization, _lblCapacity declared in main file

    // Results — utilisation bar
    // _pnlUtilBg, _pnlUtilFill declared in main file

    // Results — risk flags
    private Label _lblRisksHeader          = null!;
    // _pnlRisks declared in main file

    // Results — task breakdown
    private Label _lblTasksHeader          = null!;
    // _dgvTasks declared in main file

    // Row 3: Action buttons panel
    private Panel _pnlActions              = null!;
    // _btnSaveDraft, _btnExcel, _btnWord, _btnPdf declared in main file
    private Label _lblActionSep            = null!;

    // -------------------------------------------------------------------------
    // InitializeComponent
    // -------------------------------------------------------------------------

    private void InitializeComponent()
    {
        components = new System.ComponentModel.Container();
        SuspendLayout();

        // ---- UserControl base -----------------------------------------------
        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        // ---- Outer TableLayoutPanel (4 rows) --------------------------------
        _tblOuter = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 4,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        _tblOuter.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // row 0: header
        _tblOuter.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));   // row 1: calculate
        _tblOuter.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // row 2: results
        _tblOuter.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));   // row 3: actions
        _tblOuter.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- Row 0: Header --------------------------------------------------
        _lblHeader = new Label
        {
            Text      = "Step 7: Review & Calculate",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _tblOuter.Controls.Add(_lblHeader, 0, 0);

        // ---- Row 1: Calculate button + loading indicator --------------------
        _pnlCalcRow = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
        };

        _btnCalculate = new Button
        {
            Text     = "Calculate Estimation",
            Width    = 200,
            Height   = 40,
            Location = new Point(0, 10),
            Font     = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
        };
        ThemeHelper.StyleButton(_btnCalculate, true);

        _pnlLoading = new Panel
        {
            Location  = new Point(216, 10),
            Width     = 280,
            Height    = 40,
            BackColor = Color.Transparent,
            Visible   = false,
        };
        _lblLoadingText = new Label
        {
            Text      = "Calculating, please wait...",
            Font      = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _pnlLoading.Controls.Add(_lblLoadingText);

        _pnlCalcRow.Controls.Add(_btnCalculate);
        _pnlCalcRow.Controls.Add(_pnlLoading);
        _tblOuter.Controls.Add(_pnlCalcRow, 0, 1);

        // ---- Row 2: Results panel (scrollable) ------------------------------
        _pnlResults = new Panel
        {
            Dock       = DockStyle.Fill,
            BackColor  = ThemeHelper.Background,
            AutoScroll = true,
            Visible    = false,
        };

        int y = 8;

        // Summary cards TableLayoutPanel
        _tblCards = new TableLayoutPanel
        {
            Location    = new Point(0, y),
            Height      = 90,
            ColumnCount = 7,
            RowCount    = 1,
            BackColor   = ThemeHelper.Background,
            Anchor      = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        for (int i = 0; i < 7; i++)
            _tblCards.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / 7));
        _tblCards.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        _pnlResults.Resize += (_, _) => _tblCards.Width = _pnlResults.ClientSize.Width - 2;

        // Create metric cards via ThemeHelper; extract value labels (Controls[0])
        _cardTester = ThemeHelper.CreateMetricCard("Tester Hours",    "—");
        _cardLeader = ThemeHelper.CreateMetricCard("Leader Hours",    "—");
        _cardPr     = ThemeHelper.CreateMetricCard("PR Fix Hours",    "—");
        _cardStudy  = ThemeHelper.CreateMetricCard("Study Hours",     "—");
        _cardBuffer = ThemeHelper.CreateMetricCard("Buffer Hours",    "—");
        _cardTotal  = ThemeHelper.CreateMetricCard("Grand Total (h)", "—", ThemeHelper.Accent);
        _cardDays   = ThemeHelper.CreateMetricCard("Grand Total (d)", "—", ThemeHelper.Accent);

        // Bind the value labels that the main file references
        _lblTesterHours = (Label)_cardTester.Controls[0];
        _lblLeaderHours = (Label)_cardLeader.Controls[0];
        _lblPrHours     = (Label)_cardPr.Controls[0];
        _lblStudyHours  = (Label)_cardStudy.Controls[0];
        _lblBufferHours = (Label)_cardBuffer.Controls[0];
        _lblGrandTotal  = (Label)_cardTotal.Controls[0];
        _lblGrandDays   = (Label)_cardDays.Controls[0];

        // Wrap each card in a padding panel (DockStyle.Fill so it fills the cell)
        _wrapTester = WrapInPadding(_cardTester);
        _wrapLeader = WrapInPadding(_cardLeader);
        _wrapPr     = WrapInPadding(_cardPr);
        _wrapStudy  = WrapInPadding(_cardStudy);
        _wrapBuffer = WrapInPadding(_cardBuffer);
        _wrapTotal  = WrapInPadding(_cardTotal);
        _wrapDays   = WrapInPadding(_cardDays);

        _tblCards.Controls.Add(_wrapTester, 0, 0);
        _tblCards.Controls.Add(_wrapLeader, 1, 0);
        _tblCards.Controls.Add(_wrapPr,     2, 0);
        _tblCards.Controls.Add(_wrapStudy,  3, 0);
        _tblCards.Controls.Add(_wrapBuffer, 4, 0);
        _tblCards.Controls.Add(_wrapTotal,  5, 0);
        _tblCards.Controls.Add(_wrapDays,   6, 0);

        _pnlResults.Controls.Add(_tblCards);
        y += 98;

        // Feasibility + utilisation row
        _pnlFeasRow = new Panel
        {
            Location  = new Point(0, y),
            Height    = 48,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            BackColor = ThemeHelper.Sidebar,
        };
        _pnlResults.Resize += (_, _) => _pnlFeasRow.Width = _pnlResults.ClientSize.Width - 2;

        _pnlFeasBadge = new Panel
        {
            Location  = new Point(12, 10),
            Width     = 130,
            Height    = 28,
            BackColor = ThemeHelper.Border,
        };
        _lblFeasText = new Label
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleCenter,
        };
        _pnlFeasBadge.Controls.Add(_lblFeasText);
        _pnlFeasRow.Controls.Add(_pnlFeasBadge);

        _lblUtilization = new Label
        {
            Location  = new Point(156, 0),
            Width     = 280,
            Height    = 48,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _pnlFeasRow.Controls.Add(_lblUtilization);

        _lblCapacity = new Label
        {
            Location  = new Point(448, 0),
            Width     = 280,
            Height    = 48,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _pnlFeasRow.Controls.Add(_lblCapacity);

        _pnlResults.Controls.Add(_pnlFeasRow);
        y += 56;

        // Utilisation bar
        _pnlUtilBg = new Panel
        {
            Location  = new Point(0, y),
            Height    = 6,
            BackColor = ThemeHelper.Border,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        _pnlUtilFill = new Panel
        {
            Dock      = DockStyle.Left,
            Width     = 0,
            BackColor = ThemeHelper.Accent,
        };
        _pnlUtilBg.Controls.Add(_pnlUtilFill);
        _pnlResults.Controls.Add(_pnlUtilBg);
        _pnlResults.Resize += (_, _) => _pnlUtilBg.Width = _pnlResults.ClientSize.Width - 2;
        y += 14;

        // Risk flags header + flow panel
        _lblRisksHeader = new Label
        {
            Text      = "Risk Flags",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(0, y),
            AutoSize  = true,
        };
        _pnlResults.Controls.Add(_lblRisksHeader);
        y += 24;

        _pnlRisks = new FlowLayoutPanel
        {
            Location     = new Point(0, y),
            Height       = 36,
            Anchor       = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            BackColor    = ThemeHelper.Background,
            WrapContents = false,
            AutoSize     = false,
        };
        _pnlResults.Controls.Add(_pnlRisks);
        _pnlResults.Resize += (_, _) => _pnlRisks.Width = _pnlResults.ClientSize.Width - 2;
        y += 44;

        // Task breakdown header + grid
        _lblTasksHeader = new Label
        {
            Text      = "Task Breakdown",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(0, y),
            AutoSize  = true,
        };
        _pnlResults.Controls.Add(_lblTasksHeader);
        y += 24;

        _dgvTasks = new DataGridView
        {
            Location              = new Point(0, y),
            Anchor                = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top | AnchorStyles.Bottom,
            Height                = 300,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            ReadOnly              = true,
        };
        ThemeHelper.StyleDataGridView(_dgvTasks);
        _dgvTasks.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.None;

        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText   = "Task Name",
            Name         = "Name",
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 140,
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText        = "Type",
            Name              = "Type",
            Width             = 80,
            DefaultCellStyle  = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText       = "Base Hours",
            Name             = "Base",
            Width            = 82,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText       = "DUT Mult.",
            Name             = "DutMult",
            Width            = 76,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText       = "Profile Mult.",
            Name             = "ProfMult",
            Width            = 84,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText       = "Complexity",
            Name             = "Complexity",
            Width            = 80,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText       = "Calculated (h)",
            Name             = "Calc",
            Width            = 100,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight,
                                 Font      = new Font("Segoe UI", 9f, FontStyle.Bold) },
        });

        _pnlResults.Controls.Add(_dgvTasks);
        _pnlResults.Resize += (_, _) =>
        {
            _dgvTasks.Width  = _pnlResults.ClientSize.Width - 2;
            _dgvTasks.Height = Math.Max(150, _pnlResults.ClientSize.Height - y - 8);
        };

        _pnlResults.AutoScrollMinSize = new Size(0, y + 320);

        _tblOuter.Controls.Add(_pnlResults, 0, 2);

        // ---- Row 3: Action buttons ------------------------------------------
        _pnlActions = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding   = new Padding(0, 8, 0, 8),
            Visible   = false,
        };

        _btnSaveDraft = new Button
        {
            Text     = "Save as Draft",
            Width    = 130,
            Height   = 36,
            Location = new Point(0, 8),
            Font     = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
        };
        ThemeHelper.StyleButton(_btnSaveDraft, true);

        _lblActionSep = new Label
        {
            Text      = "|",
            ForeColor = ThemeHelper.Border,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(140, 16),
            Font      = new Font("Segoe UI", 9f),
        };

        _btnExcel = new Button
        {
            Text     = "Download Excel",
            Width    = 120,
            Height   = 36,
            Location = new Point(160, 8),
        };
        ThemeHelper.StyleButton(_btnExcel, false);

        _btnWord = new Button
        {
            Text     = "Download Word",
            Width    = 120,
            Height   = 36,
            Location = new Point(290, 8),
        };
        ThemeHelper.StyleButton(_btnWord, false);

        _btnPdf = new Button
        {
            Text     = "Download PDF",
            Width    = 120,
            Height   = 36,
            Location = new Point(420, 8),
        };
        ThemeHelper.StyleButton(_btnPdf, false);

        _pnlActions.Controls.Add(_btnSaveDraft);
        _pnlActions.Controls.Add(_lblActionSep);
        _pnlActions.Controls.Add(_btnExcel);
        _pnlActions.Controls.Add(_btnWord);
        _pnlActions.Controls.Add(_btnPdf);

        _tblOuter.Controls.Add(_pnlActions, 0, 3);

        // ---- Wire controls into UserControl ---------------------------------
        Controls.Add(_tblOuter);

        ResumeLayout(false);
    }

    // -------------------------------------------------------------------------
    // Layout helper — mirrors the private WrapInPadding in the old main file
    // -------------------------------------------------------------------------

    private static Panel WrapInPadding(Panel card)
    {
        var wrapper = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding   = new Padding(3),
        };
        card.Dock = DockStyle.Fill;
        wrapper.Controls.Add(card);
        return wrapper;
    }
}
