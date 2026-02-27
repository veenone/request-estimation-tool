using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step3References : UserControl
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

    private DataGridView _dgvProjects = null!;
    private Label _lblLoading = null!;
    private Label _lblAccuracy = null!;
    private Panel _pnlAccuracy = null!;

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

        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        BuildUI();
        Load += async (_, _) => await LoadProjectsAsync();
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
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));  // info
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));  // grid
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));  // accuracy panel
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));  // loading
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        // Header
        var lblHeader = new Label
        {
            Text = "Step 3: Reference Projects",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        layout.Controls.Add(lblHeader, 0, 0);

        // Info panel
        var infoPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(12, 8, 12, 8),
        };
        var lblInfo = new Label
        {
            Text = "Select historical projects to use as a calibration baseline (optional — you may skip by leaving all unchecked).\r\n" +
                   "An accuracy ratio > 1.0 means the team typically underestimates.",
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
        };
        infoPanel.Controls.Add(lblInfo);
        layout.Controls.Add(infoPanel, 0, 1);

        // DataGridView
        _dgvProjects = new DataGridView
        {
            Dock = DockStyle.Fill,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_dgvProjects);
        _dgvProjects.ReadOnly = false;
        _dgvProjects.EditMode = DataGridViewEditMode.EditOnKeystrokeOrF2;

        var colCheck = new DataGridViewCheckBoxColumn
        {
            HeaderText = "Select",
            Name = "ColSelect",
            Width = 56,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable = DataGridViewTriState.False,
        };
        var colName = new DataGridViewTextBoxColumn
        {
            HeaderText = "Project Name",
            Name = "ColName",
            ReadOnly = true,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 160,
        };
        var colType = new DataGridViewTextBoxColumn
        {
            HeaderText = "Type",
            Name = "ColType",
            ReadOnly = true,
            Width = 90,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };
        var colEst = new DataGridViewTextBoxColumn
        {
            HeaderText = "Estimated (h)",
            Name = "ColEstimate",
            ReadOnly = true,
            Width = 100,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        };
        var colAct = new DataGridViewTextBoxColumn
        {
            HeaderText = "Actual (h)",
            Name = "ColActual",
            ReadOnly = true,
            Width = 90,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        };
        var colRatio = new DataGridViewTextBoxColumn
        {
            HeaderText = "Accuracy Ratio",
            Name = "ColRatio",
            ReadOnly = true,
            Width = 100,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        };
        var colDate = new DataGridViewTextBoxColumn
        {
            HeaderText = "Completed",
            Name = "ColDate",
            ReadOnly = true,
            Width = 96,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };

        _dgvProjects.Columns.AddRange(colCheck, colName, colType, colEst, colAct, colRatio, colDate);

        _dgvProjects.CellValueChanged += DgvProjects_CellValueChanged;
        _dgvProjects.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_dgvProjects.IsCurrentCellDirty)
                _dgvProjects.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };

        layout.Controls.Add(_dgvProjects, 0, 2);

        // Accuracy summary panel
        _pnlAccuracy = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(12, 8, 12, 8),
            Visible = false,
        };
        _lblAccuracy = new Label
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.Text,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _pnlAccuracy.Controls.Add(_lblAccuracy);
        layout.Controls.Add(_pnlAccuracy, 0, 3);

        // Loading
        _lblLoading = new Label
        {
            Text = "Loading historical projects...",
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
