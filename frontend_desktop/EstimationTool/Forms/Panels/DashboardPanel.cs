using EstimationTool.Models;
using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Dashboard panel showing high-level metrics, status summaries, and two
/// at-a-glance grids for recent estimations and recent requests.
/// All UI controls are declared in DashboardPanel.Designer.cs and wired up
/// inside InitializeComponent().
/// </summary>
public sealed partial class DashboardPanel : UserControl
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

    // Status card value labels
    private Label _lblReqNew = null!;
    private Label _lblReqInProgress = null!;
    private Label _lblReqCompleted = null!;
    private Label _lblEstDraft = null!;

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

        InitializeComponent();

        // Wire grid event handlers after InitializeComponent has created the grids
        _dgvEstimations.CellFormatting  += DgvEstimations_CellFormatting;
        _dgvEstimations.CellDoubleClick += DgvEstimations_CellDoubleClick;
        _dgvRequests.CellFormatting     += DgvRequests_CellFormatting;
        _dgvRequests.CellDoubleClick    += DgvRequests_CellDoubleClick;

        // Load data after the control has been added to the form
        HandleCreated += async (_, _) => await LoadDataAsync();
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
            _lblTotalRequests.Text    = stats.TotalRequests.ToString();
            _lblTotalEstimations.Text = stats.TotalEstimations.ToString();
            _lblAvgHours.Text         = stats.AvgGrandTotalHours > 0
                ? stats.AvgGrandTotalHours.ToString("F0")
                : "—";
            _lblApproved.Text = stats.EstimationsApproved.ToString();

            // Status cards
            _lblReqNew.Text         = stats.RequestsNew.ToString();
            _lblReqInProgress.Text  = stats.RequestsInProgress.ToString();
            _lblReqCompleted.Text   = stats.RequestsCompleted.ToString();
            _lblEstDraft.Text       = stats.EstimationsDraft.ToString();

            // Populate estimations grid
            _estimationRows = stats.RecentEstimations;
            _dgvEstimations.Rows.Clear();
            foreach (var e in _estimationRows)
            {
                var estNum = e.EstimationNumber ?? e.Id.ToString();
                var displayNum = e.Version > 1 ? $"{estNum} (v{e.Version})" : estNum;
                _dgvEstimations.Rows.Add(
                    displayNum,
                    e.ProjectName,
                    e.GrandTotalHours.ToString("F1"),
                    e.FeasibilityStatus,
                    e.Status,
                    e.AssignedToName ?? "Unassigned"
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
                    r.Status,
                    r.AssignedToName ?? "Unassigned"
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
            Text      = $"Failed to load dashboard data: {message}",
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Top,
            AutoSize  = false,
            Height    = 30,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(4, 0, 0, 0),
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
            e.CellStyle.Font      = new Font("Segoe UI", 9f, FontStyle.Bold);
            e.FormattingApplied   = true;
        }
        else if (e.ColumnIndex == 4)
        {
            e.CellStyle.ForeColor = ThemeHelper.GetStatusColor(text);
            e.FormattingApplied   = true;
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
            e.FormattingApplied   = true;
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
}
