using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class EstimationDetailPanel
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Field declarations — all controls visible in Designer
    // -------------------------------------------------------------------------

    // Outer scrollable container
    private Panel _scrollOuter = null!;

    // Status badge in header
    private Label _lblStatusBadge = null!;

    // Title label in header
    private Label _lblTitle = null!;

    // Info grid value labels
    private Label _lblProjectType = null!;
    private Label _lblDutCount = null!;
    private Label _lblProfileCount = null!;
    private Label _lblCombinations = null!;
    private Label _lblPrFixCount = null!;
    private Label _lblDelivery = null!;
    private Label _lblCreatedBy = null!;
    private Label _lblCreatedAt = null!;

    // Effort summary cards — value labels updated after load
    private Label _lblTesterHours = null!;
    private Label _lblLeaderHours = null!;
    private Label _lblGrandHours = null!;
    private Label _lblGrandDays = null!;
    private Label _lblFeasibility = null!;

    // Status workflow area — rebuilt whenever the estimation reloads
    private Panel _workflowPanel = null!;

    // Task breakdown grid
    private DataGridView _dgvTasks = null!;

    // Report buttons
    private Button _btnExcel = null!;
    private Button _btnWord = null!;
    private Button _btnPdf = null!;

    // Back button
    private Button _btnBack = null!;

    // -------------------------------------------------------------------------
    // Dispose
    // -------------------------------------------------------------------------

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    // -------------------------------------------------------------------------
    // InitializeComponent
    // -------------------------------------------------------------------------

    private void InitializeComponent()
    {
        SuspendLayout();

        // UserControl properties
        BackColor = ThemeHelper.Background;
        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // ---- Back button panel (Bottom docked — added first so it sits at bottom) ----
        _btnBack = new Button
        {
            Text = "Back to Dashboard",
            Dock = DockStyle.Bottom,
            Height = 38,
            Width = 160,
        };
        ThemeHelper.StyleButton(_btnBack, isPrimary: false);

        var backPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 52,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 6, 0, 6),
        };
        backPanel.Controls.Add(_btnBack);
        Controls.Add(backPanel);

        // ---- Outer scrollable panel (Fill docked) ----
        _scrollOuter = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(4),
        };
        Controls.Add(_scrollOuter);

        // ---- Inner vertical stack (TableLayoutPanel, 8 rows) ----
        var stack = new TableLayoutPanel
        {
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Dock = DockStyle.Top,
            BackColor = ThemeHelper.Background,
            ColumnCount = 1,
            RowCount = 8,
            Padding = new Padding(0),
        };
        stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 80));   // Row 0 — page header
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 1 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 140));  // Row 2 — info grid
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 3 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 114));  // Row 4 — effort cards
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 5 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 114));  // Row 6 — workflow panel
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 7 — spacer

        // Row 0 — Header
        stack.Controls.Add(BuildHeader(), 0, 0);

        // Row 1 — Spacer
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 1);

        // Row 2 — Info grid
        stack.Controls.Add(BuildInfoGrid(), 0, 2);

        // Row 3 — Spacer
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 3);

        // Row 4 — Effort cards
        stack.Controls.Add(BuildEffortCardsRow(), 0, 4);

        // Row 5 — Spacer
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 5);

        // Row 6 — Workflow placeholder — replaced with real content after data loads
        _workflowPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Height = 90,
        };
        stack.Controls.Add(_workflowPanel, 0, 6);

        // Row 7 — Spacer
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 7);

        _scrollOuter.Controls.Add(stack);

        // ---- Tasks section (below the stack, DockStyle.Top) ----
        var tasksSection = BuildTasksSection();
        tasksSection.Dock = DockStyle.Top;
        tasksSection.Height = 360;
        _scrollOuter.Controls.Add(tasksSection);

        // ---- Spacer between tasks and report buttons ----
        _scrollOuter.Controls.Add(new Panel
        {
            Dock = DockStyle.Top,
            Height = 8,
            BackColor = ThemeHelper.Background,
        });

        // ---- Report buttons section ----
        var reportsSection = BuildReportButtons();
        reportsSection.Dock = DockStyle.Top;
        _scrollOuter.Controls.Add(reportsSection);

        // ---- Bottom padding spacer ----
        _scrollOuter.Controls.Add(new Panel
        {
            Dock = DockStyle.Top,
            Height = 16,
            BackColor = ThemeHelper.Background,
        });

        ResumeLayout(false);
    }

    // -------------------------------------------------------------------------
    // Section builders (called only from InitializeComponent)
    // -------------------------------------------------------------------------

    private Panel BuildHeader()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 0, 0, 4),
        };

        // Status badge — updated after load
        _lblStatusBadge = new Label
        {
            Text = "—",
            AutoSize = false,
            Width = 90,
            Height = 24,
            Dock = DockStyle.Right,
            TextAlign = ContentAlignment.MiddleCenter,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            Margin = new Padding(0, 8, 0, 0),
        };

        // Main title label — updated after load
        _lblTitle = new Label
        {
            Name = "lblTitle",
            Text = "Loading...",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
            AutoEllipsis = true,
        };

        panel.Controls.Add(_lblTitle);
        panel.Controls.Add(_lblStatusBadge);

        return panel;
    }

    private Panel BuildInfoGrid()
    {
        var outer = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(14, 10, 14, 10),
        };

        // 4-column label/value grid
        var tlp = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ColumnCount = 4,
            RowCount = 2,
            Padding = new Padding(0),
        };
        for (int i = 0; i < 4; i++)
            tlp.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25f));
        tlp.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));
        tlp.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));

        // Row 0
        tlp.Controls.Add(MakeLabelPair("Project Type",  out _lblProjectType),  0, 0);
        tlp.Controls.Add(MakeLabelPair("DUT Count",     out _lblDutCount),      1, 0);
        tlp.Controls.Add(MakeLabelPair("Profile Count", out _lblProfileCount),  2, 0);
        tlp.Controls.Add(MakeLabelPair("Combinations",  out _lblCombinations),  3, 0);

        // Row 1
        tlp.Controls.Add(MakeLabelPair("PR Fix Count",       out _lblPrFixCount),  0, 1);
        tlp.Controls.Add(MakeLabelPair("Expected Delivery",  out _lblDelivery),    1, 1);
        tlp.Controls.Add(MakeLabelPair("Created By",         out _lblCreatedBy),   2, 1);
        tlp.Controls.Add(MakeLabelPair("Created At",         out _lblCreatedAt),   3, 1);

        outer.Controls.Add(tlp);
        outer.Paint += PaintSurfaceBorder;
        return outer;
    }

    private FlowLayoutPanel BuildEffortCardsRow()
    {
        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0),
        };

        var cardTester = ThemeHelper.CreateMetricCard("Total Tester Hours", "—", ThemeHelper.Accent);
        var cardLeader = ThemeHelper.CreateMetricCard("Leader Hours",        "—", ThemeHelper.StatusFinal);
        var cardGrandH = ThemeHelper.CreateMetricCard("Grand Total Hours",   "—", ThemeHelper.FeasibilityAmber);
        var cardGrandD = ThemeHelper.CreateMetricCard("Grand Total Days",    "—", ThemeHelper.StatusRevised);
        var cardFeas   = ThemeHelper.CreateMetricCard("Feasibility",         "—", ThemeHelper.FeasibilityGreen);

        _lblTesterHours = FindValueLabel(cardTester);
        _lblLeaderHours = FindValueLabel(cardLeader);
        _lblGrandHours  = FindValueLabel(cardGrandH);
        _lblGrandDays   = FindValueLabel(cardGrandD);
        _lblFeasibility = FindValueLabel(cardFeas);

        foreach (var card in new[] { cardTester, cardLeader, cardGrandH, cardGrandD, cardFeas })
        {
            card.Height = 86;
            card.Width  = 170;
            card.Margin = new Padding(0, 0, 12, 0);
            flow.Controls.Add(card);
        }

        return flow;
    }

    private Panel BuildTasksSection()
    {
        var container = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(1),
        };

        var header = new Label
        {
            Text = "Task Breakdown",
            Dock = DockStyle.Top,
            Height = 34,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };
        container.Controls.Add(header);

        _dgvTasks = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            MultiSelect = false,
        };
        ThemeHelper.StyleDataGridView(_dgvTasks);

        _dgvTasks.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColTaskName",  HeaderText = "Task Name",         FillWeight = 30 },
            new DataGridViewTextBoxColumn { Name = "ColTaskType",  HeaderText = "Type",              FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColBaseHours", HeaderText = "Base Hours",        FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColCalcHours", HeaderText = "Calculated Hours",  FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColLeadHours", HeaderText = "Leader Hours",      FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColNewStudy",  HeaderText = "New Feature Study", FillWeight = 14 }
        );

        container.Controls.Add(_dgvTasks);
        container.Paint += PaintSurfaceBorder;
        return container;
    }

    private Panel BuildReportButtons()
    {
        var outer = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(14, 10, 14, 10),
            Height = 60,
        };

        var titleLabel = new Label
        {
            Text = "Download Report",
            Dock = DockStyle.Top,
            Height = 22,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };
        outer.Controls.Add(titleLabel);

        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0),
        };

        _btnExcel = MakeReportButton("Download Excel");
        _btnWord  = MakeReportButton("Download Word");
        _btnPdf   = MakeReportButton("Download PDF");

        flow.Controls.Add(_btnExcel);
        flow.Controls.Add(_btnWord);
        flow.Controls.Add(_btnPdf);

        outer.Controls.Add(flow);
        outer.Paint += PaintSurfaceBorder;
        return outer;
    }

    // -------------------------------------------------------------------------
    // Designer-side helpers
    // -------------------------------------------------------------------------

    /// <summary>
    /// Creates a stacked caption + value label pair inside a Fill-docked panel.
    /// The <paramref name="valueLabel"/> out parameter receives the value label
    /// so callers can update it at runtime.
    /// </summary>
    private static Panel MakeLabelPair(string caption, out Label valueLabel)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 2, 12, 2),
        };

        var captionLbl = new Label
        {
            Text = caption,
            Dock = DockStyle.Top,
            Height = 18,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8f),
            TextAlign = ContentAlignment.BottomLeft,
            AutoSize = false,
        };

        var valLbl = new Label
        {
            Text = "—",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 10f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize = false,
            AutoEllipsis = true,
        };

        panel.Controls.Add(valLbl);
        panel.Controls.Add(captionLbl);

        valueLabel = valLbl;
        return panel;
    }

    /// <summary>
    /// Creates a styled report download button with a fixed size.
    /// </summary>
    private static Button MakeReportButton(string text)
    {
        var btn = new Button
        {
            Text = text,
            Height = 36,
            Width = 148,
            Margin = new Padding(0, 0, 10, 0),
        };
        ThemeHelper.StyleButton(btn, isPrimary: false);
        return btn;
    }

    /// <summary>
    /// Finds the Fill-docked value label inside a metric card panel created by
    /// <see cref="ThemeHelper.CreateMetricCard"/>.
    /// </summary>
    private static Label FindValueLabel(Panel card)
    {
        foreach (Control c in card.Controls)
        {
            if (c is Label lbl && lbl.Dock == DockStyle.Fill)
                return lbl;
        }
        return (Label)card.Controls[0];
    }

    /// <summary>
    /// Paints a 1-pixel border around a Surface-colored panel.
    /// Attach to a <see cref="Panel.Paint"/> event.
    /// </summary>
    private static void PaintSurfaceBorder(object? sender, PaintEventArgs e)
    {
        if (sender is not Panel p) return;
        using var pen = new Pen(ThemeHelper.Border, 1f);
        e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
    }
}
