using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step3References : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class HistoryResponse
    {
        [JsonPropertyName("projects")] public List<HistoricalProject> Projects { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly WizardPanel.WizardState _state;

    private List<HistoricalProject> _projects = new();

    private const int ColCheck    = 0;
    private const int ColName     = 1;
    private const int ColType     = 2;
    private const int ColEstimate = 3;
    private const int ColActual   = 4;
    private const int ColRatio    = 5;
    private const int ColDate     = 6;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step3References(BackendApiService ipc, WizardPanel.WizardState state)
    {
        _ipc   = ipc;
        _state = state;

        InitializeComponent();

        // Wire grid events
        _dgvProjects.CellValueChanged += DgvProjects_CellValueChanged;
        _dgvProjects.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_dgvProjects.IsCurrentCellDirty)
                _dgvProjects.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };

        Load += async (_, _) => await LoadProjectsAsync();
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadProjectsAsync()
    {
        try
        {
            var resp = await _ipc.SendCommandAsync<HistoryResponse>("get_historical_projects");
            _projects = resp.Projects;

            if (InvokeRequired)
                BeginInvoke(PopulateGrid);
            else
                PopulateGrid();
        }
        catch (Exception ex)
        {
            if (InvokeRequired)
                BeginInvoke(() =>
                {
                    _lblLoading.Text = $"Error loading history: {ex.Message}";
                    _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
                });
            else
            {
                _lblLoading.Text = $"Error loading history: {ex.Message}";
                _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
            }
        }
    }

    private void PopulateGrid()
    {
        _dgvProjects.Rows.Clear();

        foreach (var proj in _projects)
        {
            bool isSelected = _state.ReferenceProjectIds.Contains(proj.Id);

            double? ratio = null;
            string ratioText = "N/A";
            if (proj.EstimatedHours.HasValue && proj.EstimatedHours > 0 && proj.ActualHours.HasValue)
            {
                ratio = proj.ActualHours.Value / proj.EstimatedHours.Value;
                ratioText = $"{ratio:F2}x";
            }

            int rowIdx = _dgvProjects.Rows.Add(
                isSelected,
                proj.ProjectName,
                proj.ProjectType,
                proj.EstimatedHours.HasValue ? $"{proj.EstimatedHours:F0}" : "N/A",
                proj.ActualHours.HasValue    ? $"{proj.ActualHours:F0}"    : "N/A",
                ratioText,
                proj.CompletionDate ?? "");

            _dgvProjects.Rows[rowIdx].Tag = proj;

            // Colour the ratio cell
            if (ratio.HasValue)
            {
                var cell = _dgvProjects.Rows[rowIdx].Cells[ColRatio];
                cell.Style.ForeColor = ratio >= 1.3 ? ThemeHelper.FeasibilityRed
                                     : ratio >= 1.0 ? ThemeHelper.FeasibilityAmber
                                     : ThemeHelper.FeasibilityGreen;
            }
        }

        _lblLoading.Text = _projects.Count == 0 ? "No historical projects found." : "";
        UpdateAccuracySummary();
    }

    // -------------------------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------------------------

    private void DgvProjects_CellValueChanged(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0 || e.ColumnIndex != ColCheck) return;
        UpdateAccuracySummary();
    }

    private void UpdateAccuracySummary()
    {
        var selectedRatios = new List<double>();

        foreach (DataGridViewRow row in _dgvProjects.Rows)
        {
            if (row.Tag is not HistoricalProject proj) continue;
            bool selected = Convert.ToBoolean(row.Cells[ColCheck].Value);
            if (!selected) continue;

            if (proj.EstimatedHours.HasValue && proj.EstimatedHours > 0 && proj.ActualHours.HasValue)
                selectedRatios.Add(proj.ActualHours.Value / proj.EstimatedHours.Value);
        }

        if (selectedRatios.Count == 0)
        {
            _pnlAccuracy.Visible = false;
            return;
        }

        double avgRatio = selectedRatios.Average();
        string trend = avgRatio > 1.15 ? " — team tends to UNDERESTIMATE"
                     : avgRatio < 0.85 ? " — team tends to OVERESTIMATE"
                     : " — estimation accuracy is good";

        _lblAccuracy.Text = $"{selectedRatios.Count} reference project(s) selected  |  " +
                            $"Average accuracy ratio: {avgRatio:F2}x{trend}";

        _lblAccuracy.ForeColor = avgRatio > 1.3 ? ThemeHelper.FeasibilityRed
                               : avgRatio > 1.0 ? ThemeHelper.FeasibilityAmber
                               : ThemeHelper.FeasibilityGreen;

        _pnlAccuracy.Visible = true;
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.ReferenceProjectIds.Clear();

        foreach (DataGridViewRow row in _dgvProjects.Rows)
        {
            if (row.Tag is not HistoricalProject proj) continue;
            if (Convert.ToBoolean(row.Cells[ColCheck].Value))
                state.ReferenceProjectIds.Add(proj.Id);
        }
    }
}
