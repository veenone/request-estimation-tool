using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step2Features : UserControl
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

    // Main features grid
    private DataGridView _dgvFeatures = null!;

    // Column indices
    private const int ColCheck    = 0;
    private const int ColNew      = 1;
    private const int ColName     = 2;
    private const int ColCategory = 3;
    private const int ColWeight   = 4;

    private Label _lblLoading = null!;
    private Label _lblInfo    = null!;
    private Label _lblSummary = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step2Features(BackendApiService ipc, WizardPanel.WizardState state)
    {
        _ipc   = ipc;
        _state = state;

        Dock       = DockStyle.Fill;
        BackColor  = ThemeHelper.Background;
        AutoScroll = true;

        BuildUI();
        Load += async (_, _) => await LoadFeaturesAsync();
    }

    // -------------------------------------------------------------------------
    // UI construction
    // -------------------------------------------------------------------------

    private void BuildUI()
    {
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 5,
            ColumnCount = 1,
            BackColor = ThemeHelper.Background,
        };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));  // header
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));  // info bar
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));  // grid
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));  // summary
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));  // loading
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        // Header
        var lblHeader = new Label
        {
            Text = "Step 2: Select Features",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        layout.Controls.Add(lblHeader, 0, 0);

        // Info bar
        _lblInfo = new Label
        {
            Text = "  Check features to include. Mark \"New\" for features that need study time (16h study + 24h test creation).",
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = ThemeHelper.Sidebar,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };
        layout.Controls.Add(_lblInfo, 0, 1);

        // Features DataGridView
        _dgvFeatures = new DataGridView
        {
            Dock = DockStyle.Fill,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            ReadOnly = false,
            MultiSelect = false,
        };
        ThemeHelper.StyleDataGridView(_dgvFeatures);

        // Override: allow checkbox columns to be editable
        _dgvFeatures.ReadOnly = false;
        _dgvFeatures.EditMode = DataGridViewEditMode.EditOnKeystrokeOrF2;

        // Column: Select
        var colSelect = new DataGridViewCheckBoxColumn
        {
            HeaderText = "Select",
            Name = "ColSelect",
            Width = 56,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable = DataGridViewTriState.False,
        };

        // Column: New Feature
        var colNew = new DataGridViewCheckBoxColumn
        {
            HeaderText = "New Feature",
            Name = "ColNew",
            Width = 88,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable = DataGridViewTriState.False,
            ToolTipText = "Mark features that have no existing tests — adds study (16h) + test creation (24h) tasks",
        };

        // Column: Name
        var colName = new DataGridViewTextBoxColumn
        {
            HeaderText = "Feature Name",
            Name = "ColName",
            ReadOnly = true,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 160,
        };

        // Column: Category
        var colCategory = new DataGridViewTextBoxColumn
        {
            HeaderText = "Category",
            Name = "ColCategory",
            ReadOnly = true,
            Width = 110,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };

        // Column: Complexity
        var colWeight = new DataGridViewTextBoxColumn
        {
            HeaderText = "Complexity",
            Name = "ColWeight",
            ReadOnly = true,
            Width = 90,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        };

        _dgvFeatures.Columns.AddRange(colSelect, colNew, colName, colCategory, colWeight);

        _dgvFeatures.CellValueChanged += DgvFeatures_CellValueChanged;
        _dgvFeatures.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_dgvFeatures.IsCurrentCellDirty)
                _dgvFeatures.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };

        layout.Controls.Add(_dgvFeatures, 0, 2);

        // Summary label
        _lblSummary = new Label
        {
            Text = "",
            Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Accent,
            BackColor = ThemeHelper.Sidebar,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };
        layout.Controls.Add(_lblSummary, 0, 3);

        // Loading label
        _lblLoading = new Label
        {
            Text = "Loading features...",
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = ThemeHelper.Background,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };
        layout.Controls.Add(_lblLoading, 0, 4);
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
            bool sel = Convert.ToBoolean(row.Cells[ColCheck].Value);
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
