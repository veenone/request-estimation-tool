using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class DashboardPanel
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Field declarations — all controls visible to the Designer
    // -------------------------------------------------------------------------

    // Outer vertical stack
    private TableLayoutPanel _stack = null!;

    // Row 0 — header
    private Panel _pnlHeader = null!;
    private Label _lblHeader = null!;

    // Row 1 — primary metric cards (FlowLayoutPanel + 4 cards)
    private FlowLayoutPanel _flowMetrics = null!;
    private Panel _cardTotalReq = null!;
    private Panel _cardTotalEst = null!;
    private Panel _cardAvgHours = null!;
    private Panel _cardApproved = null!;

    // Row 2 — status summary cards (FlowLayoutPanel + 4 cards)
    private FlowLayoutPanel _flowStatus = null!;
    private Panel _cardReqNew = null!;
    private Panel _cardReqInProgress = null!;
    private Panel _cardReqCompleted = null!;
    private Panel _cardEstDraft = null!;

    // Row 3 — grids split panel
    private TableLayoutPanel _splitGrids = null!;

    // Estimations grid container + grid
    private Panel _pnlEstimations = null!;
    private Label _lblEstimationsHeader = null!;
    private DataGridView _dgvEstimations = null!;

    // Requests grid container + grid
    private Panel _pnlRequests = null!;
    private Label _lblRequestsHeader = null!;
    private DataGridView _dgvRequests = null!;

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

        // ------------------------------------------------------------------
        // UserControl base properties
        // ------------------------------------------------------------------
        BackColor = ThemeHelper.Background;
        Dock      = DockStyle.Fill;
        Padding   = new Padding(0);
        AutoScroll = true;

        // ------------------------------------------------------------------
        // Row 0 — header panel
        // ------------------------------------------------------------------
        _lblHeader = new Label
        {
            Text      = "Dashboard",
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };

        _pnlHeader = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding   = new Padding(0, 0, 0, 8),
        };
        _pnlHeader.Controls.Add(_lblHeader);

        // ------------------------------------------------------------------
        // Row 1 — primary metric cards
        // ------------------------------------------------------------------
        _cardTotalReq  = ThemeHelper.CreateMetricCard("Total Requests",    "—", ThemeHelper.Accent);
        _cardTotalEst  = ThemeHelper.CreateMetricCard("Total Estimations", "—", ThemeHelper.FeasibilityGreen);
        _cardAvgHours  = ThemeHelper.CreateMetricCard("Avg Hours",         "—", ThemeHelper.FeasibilityAmber);
        _cardApproved  = ThemeHelper.CreateMetricCard("Approved",          "—", ThemeHelper.StatusApproved);

        _lblTotalRequests    = FindValueLabel(_cardTotalReq);
        _lblTotalEstimations = FindValueLabel(_cardTotalEst);
        _lblAvgHours         = FindValueLabel(_cardAvgHours);
        _lblApproved         = FindValueLabel(_cardApproved);

        foreach (var card in new[] { _cardTotalReq, _cardTotalEst, _cardAvgHours, _cardApproved })
        {
            card.Margin = new Padding(0, 0, 12, 0);
            card.Height = 90;
            card.Width  = 200;
        }

        _flowMetrics = new FlowLayoutPanel
        {
            Dock          = DockStyle.Fill,
            BackColor     = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents  = false,
            Padding       = new Padding(0, 0, 0, 8),
        };
        _flowMetrics.Controls.AddRange(new Control[]
        {
            _cardTotalReq, _cardTotalEst, _cardAvgHours, _cardApproved,
        });

        // ------------------------------------------------------------------
        // Row 2 — status summary cards
        // ------------------------------------------------------------------
        (_lblReqNew,        _cardReqNew)        = BuildSmallStatusCard("Requests: New",         "—", ThemeHelper.Accent);
        (_lblReqInProgress, _cardReqInProgress) = BuildSmallStatusCard("Requests: In Progress", "—", ThemeHelper.FeasibilityAmber);
        (_lblReqCompleted,  _cardReqCompleted)  = BuildSmallStatusCard("Requests: Completed",   "—", ThemeHelper.FeasibilityGreen);
        (_lblEstDraft,      _cardEstDraft)      = BuildSmallStatusCard("Estimations: Draft",    "—", ThemeHelper.StatusDraft);

        foreach (var card in new[] { _cardReqNew, _cardReqInProgress, _cardReqCompleted, _cardEstDraft })
        {
            card.Margin = new Padding(0, 0, 12, 0);
            card.Height = 76;
            card.Width  = 210;
        }

        _flowStatus = new FlowLayoutPanel
        {
            Dock          = DockStyle.Fill,
            BackColor     = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents  = false,
            Padding       = new Padding(0, 0, 0, 10),
        };
        _flowStatus.Controls.AddRange(new Control[]
        {
            _cardReqNew, _cardReqInProgress, _cardReqCompleted, _cardEstDraft,
        });

        // ------------------------------------------------------------------
        // Row 3 — estimations grid
        // ------------------------------------------------------------------
        _lblEstimationsHeader = new Label
        {
            Text      = "Recent Estimations",
            Dock      = DockStyle.Top,
            Height    = 38,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        _dgvEstimations = new DataGridView
        {
            Dock               = DockStyle.Fill,
            ReadOnly           = true,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            MultiSelect        = false,
        };
        ThemeHelper.StyleDataGridView(_dgvEstimations);
        _dgvEstimations.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColEstNum",         HeaderText = "#",           FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColEstProject",     HeaderText = "Project",     FillWeight = 36 },
            new DataGridViewTextBoxColumn { Name = "ColEstHours",       HeaderText = "Hours",       FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColEstFeasibility", HeaderText = "Feasibility", FillWeight = 20 },
            new DataGridViewTextBoxColumn { Name = "ColEstStatus",      HeaderText = "Status",      FillWeight = 16 }
        );

        _pnlEstimations = CreateGridContainer(_lblEstimationsHeader);
        _pnlEstimations.Controls.Add(_dgvEstimations);

        // ------------------------------------------------------------------
        // Row 3 — requests grid
        // ------------------------------------------------------------------
        _lblRequestsHeader = new Label
        {
            Text      = "Recent Requests",
            Dock      = DockStyle.Top,
            Height    = 38,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        _dgvRequests = new DataGridView
        {
            Dock               = DockStyle.Fill,
            ReadOnly           = true,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            MultiSelect        = false,
        };
        ThemeHelper.StyleDataGridView(_dgvRequests);
        _dgvRequests.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColReqNum",      HeaderText = "#",        FillWeight = 16 },
            new DataGridViewTextBoxColumn { Name = "ColReqTitle",    HeaderText = "Title",    FillWeight = 46 },
            new DataGridViewTextBoxColumn { Name = "ColReqPriority", HeaderText = "Priority", FillWeight = 20 },
            new DataGridViewTextBoxColumn { Name = "ColReqStatus",   HeaderText = "Status",   FillWeight = 18 }
        );

        _pnlRequests = CreateGridContainer(_lblRequestsHeader);
        _pnlRequests.Controls.Add(_dgvRequests);

        // ------------------------------------------------------------------
        // Row 3 — side-by-side split panel
        // ------------------------------------------------------------------
        _splitGrids = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            BackColor   = ThemeHelper.Background,
            ColumnCount = 2,
            RowCount    = 1,
            Padding     = new Padding(0),
        };
        _splitGrids.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 55f));
        _splitGrids.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 45f));
        _splitGrids.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
        _splitGrids.Controls.Add(_pnlEstimations, 0, 0);
        _splitGrids.Controls.Add(_pnlRequests,    1, 0);

        // ------------------------------------------------------------------
        // Outer vertical stack
        // ------------------------------------------------------------------
        _stack = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            BackColor   = ThemeHelper.Background,
            ColumnCount = 1,
            RowCount    = 5,
            Padding     = new Padding(4),
        };
        _stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        _stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));   // Row 0 — Header
        _stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 114));  // Row 1 — Primary metric cards
        _stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 94));   // Row 2 — Status cards
        _stack.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));  // Row 3 — Grids
        _stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 4 — Bottom spacer

        _stack.Controls.Add(_pnlHeader,    0, 0);
        _stack.Controls.Add(_flowMetrics,  0, 1);
        _stack.Controls.Add(_flowStatus,   0, 2);
        _stack.Controls.Add(_splitGrids,   0, 3);

        Controls.Add(_stack);

        ResumeLayout(false);
    }

    // -------------------------------------------------------------------------
    // UI-creation helpers (support InitializeComponent; kept here so the
    // Designer file is self-contained)
    // -------------------------------------------------------------------------

    /// <summary>
    /// Builds a small status card and returns both the live value Label and
    /// the card Panel so that InitializeComponent can store both as fields.
    /// </summary>
    private static (Label valueLabel, Panel card) BuildSmallStatusCard(
        string title, string value, Color accent)
    {
        var card = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding   = new Padding(12, 6, 12, 6),
        };

        var titleLbl = new Label
        {
            Text      = title,
            Dock      = DockStyle.Top,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font      = new Font("Segoe UI", 8.5f),
            AutoSize  = false,
            Height    = 22,
            TextAlign = ContentAlignment.BottomLeft,
        };

        var valueLbl = new Label
        {
            Text      = value,
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 14f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize  = false,
        };

        card.Controls.Add(valueLbl);
        card.Controls.Add(titleLbl);

        card.Paint += (sender, e) =>
        {
            if (sender is not Panel p) return;
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using var borderPen = new Pen(ThemeHelper.Border, 1f);
            var rect = new Rectangle(0, 0, p.Width - 1, p.Height - 1);
            DrawRoundedRect(e.Graphics, borderPen, rect, 5);
            using var accentBrush = new SolidBrush(accent);
            e.Graphics.FillRectangle(accentBrush, new Rectangle(0, 4, 3, p.Height - 8));
        };

        return (valueLbl, card);
    }

    /// <summary>
    /// Returns a Surface-coloured panel with the provided header Label already
    /// docked to the top and a border Paint handler wired up.
    /// The caller is responsible for adding the DataGridView as a Fill-docked child.
    /// </summary>
    private static Panel CreateGridContainer(Label headerLabel)
    {
        var panel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            Padding   = new Padding(1),
            Margin    = new Padding(0, 0, 8, 0),
        };

        panel.Controls.Add(headerLabel);

        panel.Paint += (sender, e) =>
        {
            if (sender is not Panel p) return;
            using var pen = new Pen(ThemeHelper.Border, 1f);
            e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
        };

        return panel;
    }

    /// <summary>
    /// Draws a rounded rectangle using the supplied Graphics, Pen, bounds, and corner radius.
    /// </summary>
    private static void DrawRoundedRect(Graphics g, Pen pen, Rectangle bounds, int radius)
    {
        int d = radius * 2;
        using var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(bounds.X,          bounds.Y,          d, d, 180, 90);
        path.AddArc(bounds.Right - d,  bounds.Y,          d, d, 270, 90);
        path.AddArc(bounds.Right - d,  bounds.Bottom - d, d, d,   0, 90);
        path.AddArc(bounds.X,          bounds.Bottom - d, d, d,  90, 90);
        path.CloseFigure();
        g.DrawPath(pen, path);
    }

    /// <summary>
    /// CreateMetricCard places the value Label with DockStyle.Fill first, then
    /// the title Label with DockStyle.Top on top of it. This helper returns the
    /// fill-docked label so callers can update the displayed value at runtime.
    /// </summary>
    private static Label FindValueLabel(Panel card)
    {
        foreach (Control c in card.Controls)
        {
            if (c is Label lbl && lbl.Dock == DockStyle.Fill)
                return lbl;
        }

        // Fallback — should never reach here with the current ThemeHelper implementation
        return (Label)card.Controls[0];
    }
}
