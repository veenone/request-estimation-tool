using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step2Features : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class FeaturesResponse
    {
        [JsonPropertyName("features")] public List<Feature> Features { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly WizardPanel.WizardState _state;

    private List<Feature> _allFeatures = new();

    // Column indices
    private const int ColCheck    = 0;
    private const int ColNew      = 1;
    private const int ColName     = 2;
    private const int ColCategory = 3;
    private const int ColWeight   = 4;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step2Features(BackendApiService ipc, WizardPanel.WizardState state)
    {
        _ipc   = ipc;
        _state = state;

        InitializeComponent();

        // Wire grid events
        _dgvFeatures.CellValueChanged += DgvFeatures_CellValueChanged;
        _dgvFeatures.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_dgvFeatures.IsCurrentCellDirty)
                _dgvFeatures.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };

        Load += async (_, _) => await LoadFeaturesAsync();
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadFeaturesAsync()
    {
        try
        {
            var resp = await _ipc.SendCommandAsync<FeaturesResponse>("get_features");
            _allFeatures = resp.Features;

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
                    _lblLoading.Text = $"Error loading features: {ex.Message}";
                    _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
                });
            else
            {
                _lblLoading.Text = $"Error loading features: {ex.Message}";
                _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
            }
        }
    }

    private void PopulateGrid()
    {
        _dgvFeatures.Rows.Clear();

        foreach (var feature in _allFeatures)
        {
            bool isSelected  = _state.SelectedFeatureIds.Contains(feature.Id);
            bool isNew       = _state.NewFeatureIds.Contains(feature.Id);

            // Default new features to checked if they have no existing tests and are selected
            bool defaultNew = !feature.HasExistingTests && isSelected;

            int rowIdx = _dgvFeatures.Rows.Add(
                isSelected,
                isNew || defaultNew,
                feature.Name,
                feature.Category ?? "General",
                $"{feature.ComplexityWeight:F1}x");

            _dgvFeatures.Rows[rowIdx].Tag = feature;

            // Dim "New Feature" cell if not selected
            UpdateNewCellStyle(rowIdx, isSelected);
        }

        _lblLoading.Text = "";
        UpdateSummary();
    }

    // -------------------------------------------------------------------------
    // Grid event handlers
    // -------------------------------------------------------------------------

    private void DgvFeatures_CellValueChanged(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0) return;

        if (e.ColumnIndex == ColCheck)
        {
            bool selected = Convert.ToBoolean(_dgvFeatures.Rows[e.RowIndex].Cells[ColCheck].Value);
            UpdateNewCellStyle(e.RowIndex, selected);

            // When deselecting, also uncheck New
            if (!selected)
                _dgvFeatures.Rows[e.RowIndex].Cells[ColNew].Value = false;
        }

        UpdateSummary();
    }

    private void UpdateNewCellStyle(int rowIdx, bool isSelected)
    {
        var cell = _dgvFeatures.Rows[rowIdx].Cells[ColNew];
        if (!isSelected)
        {
            cell.Style.BackColor = ThemeHelper.Sidebar;
            cell.ReadOnly = true;
        }
        else
        {
            cell.Style.BackColor = ThemeHelper.Surface;
            cell.ReadOnly = false;
        }
    }

    private void UpdateSummary()
    {
        int selectedCount = 0;
        int newCount      = 0;

        foreach (DataGridViewRow row in _dgvFeatures.Rows)
        {
            bool sel   = Convert.ToBoolean(row.Cells[ColCheck].Value);
            bool isNew = Convert.ToBoolean(row.Cells[ColNew].Value);
            if (sel) selectedCount++;
            if (sel && isNew) newCount++;
        }

        _lblSummary.Text = selectedCount == 0
            ? "No features selected"
            : $"{selectedCount} feature(s) selected  |  {newCount} marked as new (study + test creation tasks will be added)";
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public bool Validate(out string error)
    {
        int selected = _dgvFeatures.Rows.Cast<DataGridViewRow>()
            .Count(r => Convert.ToBoolean(r.Cells[ColCheck].Value));

        if (selected == 0)
        {
            error = "Please select at least one feature.";
            return false;
        }

        error = "";
        return true;
    }

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.SelectedFeatureIds.Clear();
        state.NewFeatureIds.Clear();

        foreach (DataGridViewRow row in _dgvFeatures.Rows)
        {
            if (row.Tag is not Feature feature) continue;

            bool selected = Convert.ToBoolean(row.Cells[ColCheck].Value);
            bool isNew    = Convert.ToBoolean(row.Cells[ColNew].Value);

            if (selected)
            {
                state.SelectedFeatureIds.Add(feature.Id);
                if (isNew)
                    state.NewFeatureIds.Add(feature.Id);
            }
        }
    }
}
