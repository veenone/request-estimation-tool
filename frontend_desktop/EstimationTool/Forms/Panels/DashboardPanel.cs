using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Dashboard panel showing high-level metrics, status summaries, and two
/// at-a-glance grids for recent estimations and recent requests.
/// All UI is built programmatically — no designer file.
/// </summary>
public sealed class DashboardPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly MainForm _mainForm;

    // Metric card value labels — updated after data loads
    private Label _lblTotalRequests = null!;
    private Label _lblTotalEstimations = null!;
    private Label _lblAvgHours = null!;
    private Label _lblApproved = null!;

    // Status cards
    private Label _lblReqNew = null!;
    private Label _lblReqInProgress = null!;
    private Label _lblReqCompleted = null!;
    private Label _lblEstDraft = null!;

    // Data grids
    private DataGridView _dgvEstimations = null!;
    private DataGridView _dgvRequests = null!;

    // Cached row data so double-click can look up IDs
    private List<RecentEstimation> _estimationRows = new();
    private List<RecentRequest> _requestRows = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public DashboardPanel(BackendApiService ipc, MainForm mainForm)
    {
        _ipc = ipc;
        _mainForm = mainForm;

        BackColor = ThemeHelper.Background;
        Dock = DockStyle.Fill;
        Padding = new Padding(0);
        AutoScroll = true;

        BuildLayout();

        // Load data after the control has been added to the form
        HandleCreated += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Layout construction
    // -------------------------------------------------------------------------

    private void BuildLayout()
    {
        // Outer vertical stack panel
        var stack = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            ColumnCount = 1,
            RowCount = 5,
            Padding = new Padding(4),
        };
        stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));   // Header
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 100));  // Primary metric cards
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 80));   // Status cards
        stack.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));  // Grids
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Bottom spacer
        Controls.Add(stack);

        // Row 0 — page header
        stack.Controls.Add(BuildHeader(), 0, 0);

        // Row 1 — four primary metric cards
        stack.Controls.Add(BuildPrimaryMetricRow(), 0, 1);

        // Row 2 — four status summary cards
        stack.Controls.Add(BuildStatusCardRow(), 0, 2);

        // Row 3 — side-by-side grids
        stack.Controls.Add(BuildGridsRow(), 0, 3);
    }

    private static Panel BuildHeader()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 0, 0, 8),
        };

        var lbl = new Label
        {
            Text = "Dashboard",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };

        panel.Controls.Add(lbl);
        return panel;
    }

    private Panel BuildPrimaryMetricRow()
    {
        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 0, 0, 8),
        };

        // We keep references to the value labels so we can update them.
        // CreateMetricCard returns a Panel; we find the value label by index.
        var cardTotalReq = ThemeHelper.CreateMetricCard("Total Requests", "—", ThemeHelper.Accent);
        var cardTotalEst = ThemeHelper.CreateMetricCard("Total Estimations", "—", ThemeHelper.FeasibilityGreen);
        var cardAvgHours = ThemeHelper.CreateMetricCard("Avg Hours", "—", ThemeHelper.FeasibilityAmber);
        var cardApproved = ThemeHelper.CreateMetricCard("Approved", "—", ThemeHelper.StatusApproved);

        // The value Label has DockStyle.Fill and is added first (index 0 in Controls,
        // because titleLabel is added second with DockStyle.Top and stacks above it).
        _lblTotalRequests = FindValueLabel(cardTotalReq);
        _lblTotalEstimations = FindValueLabel(cardTotalEst);
        _lblAvgHours = FindValueLabel(cardAvgHours);
        _lblApproved = FindValueLabel(cardApproved);

        foreach (var card in new[] { cardTotalReq, cardTotalEst, cardAvgHours, cardApproved })
        {
            card.Margin = new Padding(0, 0, 12, 0);
            // Size the card proportionally at runtime; give it a fixed height here
            card.Height = 76;
            card.Width = 180;
            flow.Controls.Add(card);
        }

        return flow;
    }

    private Panel BuildStatusCardRow()
    {
        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 0, 0, 10),
        };

        // Requests: New, In Progress, Completed — Estimations: Draft
        (_lblReqNew, var c1) = BuildSmallStatusCard("Requests: New", "—", ThemeHelper.Accent);
        (_lblReqInProgress, var c2) = BuildSmallStatusCard("Requests: In Progress", "—", ThemeHelper.FeasibilityAmber);
        (_lblReqCompleted, var c3) = BuildSmallStatusCard("Requests: Completed", "—", ThemeHelper.FeasibilityGreen);
        (_lblEstDraft, var c4) = BuildSmallStatusCard("Estimations: Draft", "—", ThemeHelper.StatusDraft);

        foreach (var card in new[] { c1, c2, c3, c4 })
        {
            card.Margin = new Padding(0, 0, 12, 0);
            card.Height = 62;
            card.Width = 190;
            flow.Controls.Add(card);
        }

        return flow;
    }

    private static (Label valueLabel, Panel card) BuildSmallStatusCard(string title, string value, Color accent)
    {
        var card = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(12, 6, 12, 6),
        };

        var titleLbl = new Label
        {
            Text = title,
            Dock = DockStyle.Top,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8f),
            AutoSize = false,
            Height = 18,
            TextAlign = ContentAlignment.BottomLeft,
        };

        var valueLbl = new Label
        {
            Text = value,
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 14f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize = false,
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

    private Panel BuildGridsRow()
    {
        var split = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            ColumnCount = 2,
            RowCount = 1,
            Padding = new Padding(0),
        };
        split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 55f));
        split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 45f));
        split.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

        split.Controls.Add(BuildEstimationsGrid(), 0, 0);
        split.Controls.Add(BuildRequestsGrid(), 1, 0);

        return split;
    }

    private Panel BuildEstimationsGrid()
    {
        var container = CreateGridContainer("Recent Estimations");

        _dgvEstimations = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            MultiSelect = false,
        };

        ThemeHelper.StyleDataGridView(_dgvEstimations);

        _dgvEstimations.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColEstNum",         HeaderText = "#",           FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColEstProject",     HeaderText = "Project",     FillWeight = 36 },
            new DataGridViewTextBoxColumn { Name = "ColEstHours",       HeaderText = "Hours",       FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColEstFeasibility", HeaderText = "Feasibility", FillWeight = 20 },
            new DataGridViewTextBoxColumn { Name = "ColEstStatus",      HeaderText = "Status",      FillWeight = 16 }
        );

        _dgvEstimations.CellFormatting += DgvEstimations_CellFormatting;
        _dgvEstimations.CellDoubleClick += DgvEstimations_CellDoubleClick;

        container.Controls.Add(_dgvEstimations);
        return container;
    }

    private Panel BuildRequestsGrid()
    {
        var container = CreateGridContainer("Recent Requests");

        _dgvRequests = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            MultiSelect = false,
        };

        ThemeHelper.StyleDataGridView(_dgvRequests);

        _dgvRequests.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColReqNum",      HeaderText = "#",        FillWeight = 16 },
            new DataGridViewTextBoxColumn { Name = "ColReqTitle",    HeaderText = "Title",    FillWeight = 46 },
            new DataGridViewTextBoxColumn { Name = "ColReqPriority", HeaderText = "Priority", FillWeight = 20 },
            new DataGridViewTextBoxColumn { Name = "ColReqStatus",   HeaderText = "Status",   FillWeight = 18 }
        );

        _dgvRequests.CellFormatting += DgvRequests_CellFormatting;
        _dgvRequests.CellDoubleClick += DgvRequests_CellDoubleClick;

        container.Controls.Add(_dgvRequests);
        return container;
    }

    /// <summary>
    /// Returns a Surface-coloured panel with a section title label at the top.
    /// The caller adds the DataGridView as a Fill-docked child.
    /// </summary>
    private static Panel CreateGridContainer(string title)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(1),
            Margin = new Padding(0, 0, 8, 0),
        };

        var header = new Label
        {
            Text = title,
            Dock = DockStyle.Top,
            Height = 32,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };

        panel.Controls.Add(header);

        panel.Paint += (sender, e) =>
        {
            if (sender is not Panel p) return;
            using var pen = new Pen(ThemeHelper.Border, 1f);
            e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
        };

        return panel;
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var stats = await _ipc.SendCommandAsync<DashboardStats>("get_dashboard_stats");
            UpdateUI(stats);
        }
        catch (Exception ex)
        {
            // Surface the error in a non-blocking way — show placeholder text
            if (IsDisposed) return;
            BeginInvoke(() => ShowLoadError(ex.Message));
        }
    }

    private void UpdateUI(DashboardStats stats)
    {
        if (IsDisposed) return;

        // Use BeginInvoke so this is safe whether called from UI thread or background
        Action update = () =>
        {
            if (IsDisposed) return;

            // Primary metric cards
            _lblTotalRequests.Text = stats.TotalRequests.ToString();
            _lblTotalEstimations.Text = stats.TotalEstimations.ToString();
            _lblAvgHours.Text = stats.AvgGrandTotalHours > 0
                ? stats.AvgGrandTotalHours.ToString("F0")
                : "—";
            _lblApproved.Text = stats.EstimationsApproved.ToString();

            // Status cards
            _lblReqNew.Text = stats.RequestsNew.ToString();
            _lblReqInProgress.Text = stats.RequestsInProgress.ToString();
            _lblReqCompleted.Text = stats.RequestsCompleted.ToString();
            _lblEstDraft.Text = stats.EstimationsDraft.ToString();

            // Populate estimations grid
            _estimationRows = stats.RecentEstimations;
            _dgvEstimations.Rows.Clear();
            foreach (var e in _estimationRows)
            {
                _dgvEstimations.Rows.Add(
                    e.EstimationNumber ?? e.Id.ToString(),
                    e.ProjectName,
                    e.GrandTotalHours.ToString("F1"),
                    e.FeasibilityStatus,
                    e.Status
                );
            }

            // Populate requests grid
            _requestRows = stats.RecentRequests;
            _dgvRequests.Rows.Clear();
            foreach (var r in _requestRows)
            {
                _dgvRequests.Rows.Add(
                    r.RequestNumber,
                    r.Title,
                    r.Priority,
                    r.Status
                );
            }
        };

        if (InvokeRequired)
            BeginInvoke(update);
        else
            update();
    }

    private void ShowLoadError(string message)
    {
        // Replace grid area with an error label — simple fallback
        var lbl = new Label
        {
            Text = $"Failed to load dashboard data: {message}",
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            AutoSize = false,
            Height = 30,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(4, 0, 0, 0),
        };
        Controls.Add(lbl);
        lbl.BringToFront();
    }

    // -------------------------------------------------------------------------
    // Grid event handlers
    // -------------------------------------------------------------------------

    private void DgvEstimations_CellFormatting(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.Value is not string text) return;

        // Column index 3 = Feasibility, column index 4 = Status
        if (e.ColumnIndex == 3)
        {
            e.CellStyle.ForeColor = ThemeHelper.GetFeasibilityColor(text);
            e.CellStyle.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
            e.FormattingApplied = true;
        }
        else if (e.ColumnIndex == 4)
        {
            e.CellStyle.ForeColor = ThemeHelper.GetStatusColor(text);
            e.FormattingApplied = true;
        }
    }

    private void DgvEstimations_CellDoubleClick(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0 || e.RowIndex >= _estimationRows.Count) return;
        var estimationId = _estimationRows[e.RowIndex].Id;
        _mainForm.NavigateTo("EstimationDetail", estimationId);
    }

    private void DgvRequests_CellFormatting(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.Value is not string text) return;

        // Column index 2 = Priority
        if (e.ColumnIndex == 2)
        {
            e.CellStyle.ForeColor = GetPriorityColor(text);
            e.FormattingApplied = true;
        }
    }

    private void DgvRequests_CellDoubleClick(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0) return;
        _mainForm.NavigateTo("Requests");
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Color GetPriorityColor(string priority) =>
        priority?.ToUpperInvariant() switch
        {
            "CRITICAL" => ThemeHelper.FeasibilityRed,
            "HIGH"     => ThemeHelper.FeasibilityAmber,
            "MEDIUM"   => ThemeHelper.Text,
            "LOW"      => ThemeHelper.TextSecondary,
            _          => ThemeHelper.TextSecondary,
        };

    /// <summary>
    /// CreateMetricCard adds the value Label first (DockStyle.Fill), then the
    /// title Label (DockStyle.Top). The fill label ends up at Controls[0].
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

    private static void DrawRoundedRect(Graphics g, Pen pen, Rectangle bounds, int radius)
    {
        int d = radius * 2;
        using var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        g.DrawPath(pen, path);
    }
}
