using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for viewing historical projects and adding new reference entries.
/// Read-only list with an Add button — historical records are not edited or
/// deleted because they are used for calibrating future estimates.
/// </summary>
public class HistoryPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class HistoryResponse
    {
        [JsonPropertyName("projects")]
        public List<HistoricalProject> Projects { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private readonly DataGridView _grid;
    private readonly Button _btnAdd;
    private readonly Label _headerLabel;
    private readonly Label _subtitleLabel;

    private List<HistoricalProject> _projects = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public HistoryPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // --- Header ---
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 64,
        };

        _headerLabel = new Label
        {
            Text = "Historical Projects",
            AutoSize = true,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);

        _subtitleLabel = new Label
        {
            Text = "Reference projects used for calibrating estimation accuracy.",
            AutoSize = true,
            Location = new Point(0, 32),
        };
        ThemeHelper.StyleLabel(_subtitleLabel, isHeader: false);

        headerPanel.Controls.Add(_subtitleLabel);
        headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        var toolbar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 40,
        };

        _btnAdd = new Button
        {
            Text     = "Add Historical Project",
            Width    = 170,
            Height   = 32,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleButton(_btnAdd, isPrimary: true);
        toolbar.Controls.Add(_btnAdd);

        // --- Grid ---
        _grid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            MultiSelect = false,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_grid);

        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Id",              HeaderText = "ID",               FillWeight = 6  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProjectName",     HeaderText = "Project Name",     FillWeight = 24 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProjectType",     HeaderText = "Type",             FillWeight = 11 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "EstimatedHours",  HeaderText = "Estimated Hours",  FillWeight = 13 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ActualHours",     HeaderText = "Actual Hours",     FillWeight = 11 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "DutCount",        HeaderText = "DUT Count",        FillWeight = 9  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProfileCount",    HeaderText = "Profile Count",    FillWeight = 10 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "PrCount",         HeaderText = "PR Count",         FillWeight = 8  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "CompletionDate",  HeaderText = "Completion Date",  FillWeight = 14 });

        // -------------------------------------------------------------------------
        // Layout
        // -------------------------------------------------------------------------
        Controls.Add(_grid);
        Controls.Add(toolbar);
        Controls.Add(headerPanel);

        // -------------------------------------------------------------------------
        // Events
        // -------------------------------------------------------------------------
        _btnAdd.Click += BtnAdd_Click;

        ThemeHelper.ApplyTheme(this);

        Load += async (s, e) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var response = await _ipc.SendCommandAsync<HistoryResponse>("get_historical_projects");
            _projects = response.Projects;

            _grid.Rows.Clear();
            foreach (var p in _projects)
            {
                _grid.Rows.Add(
                    p.Id,
                    p.ProjectName,
                    p.ProjectType,
                    p.EstimatedHours.HasValue ? p.EstimatedHours.Value.ToString("F1") : "",
                    p.ActualHours.HasValue    ? p.ActualHours.Value.ToString("F1")    : "",
                    p.DutCount.HasValue       ? p.DutCount.Value.ToString()           : "",
                    p.ProfileCount.HasValue   ? p.ProfileCount.Value.ToString()       : "",
                    p.PrCount.HasValue        ? p.PrCount.Value.ToString()            : "",
                    p.CompletionDate ?? "");
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load historical projects:\n{ex.Message}",
                "Load Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Button handlers
    // -------------------------------------------------------------------------

    private async void BtnAdd_Click(object? sender, EventArgs e)
    {
        using var dialog = new HistoricalProjectDialog();
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_historical_project", new
            {
                project_name     = dialog.ProjectName,
                project_type     = dialog.ProjectType,
                estimated_hours  = dialog.EstimatedHours,
                actual_hours     = dialog.ActualHours,
                dut_count        = dialog.DutCount,
                profile_count    = dialog.ProfileCount,
                pr_count         = dialog.PrCount,
                completion_date  = dialog.CompletionDate,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create historical project:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}

// =============================================================================
// Historical Project Add dialog
// =============================================================================

sealed class HistoricalProjectDialog : Form
{
    // Outputs
    public string  ProjectName     => _txtName.Text.Trim();
    public string  ProjectType     => _cmbType.SelectedItem?.ToString() ?? "EVOLUTION";
    public double? EstimatedHours  => _nudEstimated.Value > 0 ? (double?)_nudEstimated.Value : null;
    public double? ActualHours     => _nudActual.Value > 0    ? (double?)_nudActual.Value    : null;
    public int?    DutCount        => (int)_nudDuts.Value     > 0 ? (int?)_nudDuts.Value     : null;
    public int?    ProfileCount    => (int)_nudProfiles.Value > 0 ? (int?)_nudProfiles.Value : null;
    public int?    PrCount         => (int)_nudPrs.Value      > 0 ? (int?)_nudPrs.Value      : null;
    public string? CompletionDate  => _dtpCompletion.Checked
                                        ? _dtpCompletion.Value.ToString("yyyy-MM-dd")
                                        : null;

    private readonly TextBox        _txtName;
    private readonly ComboBox       _cmbType;
    private readonly NumericUpDown  _nudEstimated;
    private readonly NumericUpDown  _nudActual;
    private readonly NumericUpDown  _nudDuts;
    private readonly NumericUpDown  _nudProfiles;
    private readonly NumericUpDown  _nudPrs;
    private readonly DateTimePicker _dtpCompletion;

    private static readonly string[] ProjectTypes = ["NEW", "EVOLUTION", "SUPPORT"];

    public HistoricalProjectDialog()
    {
        Text            = "Add Historical Project";
        Size            = new Size(460, 480);
        MinimumSize     = new Size(420, 460);
        StartPosition   = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false;
        MinimizeBox     = false;
        BackColor       = ThemeHelper.Background;
        ForeColor       = ThemeHelper.Text;

        var layout = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            ColumnCount = 2,
            RowCount    = 10,
            Padding     = new Padding(16),
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        int row = 0;

        // Project name
        layout.Controls.Add(MakeLabel("Project Name *"), 0, row);
        _txtName = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtName);
        layout.Controls.Add(_txtName, 1, row++);

        // Project type
        layout.Controls.Add(MakeLabel("Project Type"), 0, row);
        _cmbType = new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList };
        _cmbType.Items.AddRange(ProjectTypes);
        _cmbType.SelectedIndex = 1; // default EVOLUTION
        ThemeHelper.StyleComboBox(_cmbType);
        layout.Controls.Add(_cmbType, 1, row++);

        // Estimated hours
        layout.Controls.Add(MakeLabel("Estimated Hours"), 0, row);
        _nudEstimated = MakeHoursUpDown();
        layout.Controls.Add(_nudEstimated, 1, row++);

        // Actual hours
        layout.Controls.Add(MakeLabel("Actual Hours"), 0, row);
        _nudActual = MakeHoursUpDown();
        layout.Controls.Add(_nudActual, 1, row++);

        // DUT count
        layout.Controls.Add(MakeLabel("DUT Count"), 0, row);
        _nudDuts = MakeCountUpDown();
        layout.Controls.Add(_nudDuts, 1, row++);

        // Profile count
        layout.Controls.Add(MakeLabel("Profile Count"), 0, row);
        _nudProfiles = MakeCountUpDown();
        layout.Controls.Add(_nudProfiles, 1, row++);

        // PR count
        layout.Controls.Add(MakeLabel("PR Count"), 0, row);
        _nudPrs = MakeCountUpDown();
        layout.Controls.Add(_nudPrs, 1, row++);

        // Completion date
        layout.Controls.Add(MakeLabel("Completion Date"), 0, row);
        _dtpCompletion = new DateTimePicker
        {
            Dock       = DockStyle.Fill,
            Format     = DateTimePickerFormat.Short,
            ShowCheckBox = true,
            Checked    = false,
            Value      = DateTime.Today,
        };
        // DateTimePicker has limited dark theming support in WinForms
        _dtpCompletion.BackColor = ThemeHelper.Surface;
        _dtpCompletion.ForeColor = ThemeHelper.Text;
        layout.Controls.Add(_dtpCompletion, 1, row++);

        // Buttons
        var btnPanel = new Panel { Dock = DockStyle.Fill };
        layout.Controls.Add(new Label(), 0, row);
        layout.Controls.Add(btnPanel, 1, row);

        var btnOk = new Button { Text = "Save", Width = 80, Height = 32, Location = new Point(0, 4) };
        ThemeHelper.StyleButton(btnOk, isPrimary: true);
        btnOk.Click += (s, e) =>
        {
            if (string.IsNullOrWhiteSpace(_txtName.Text))
            {
                MessageBox.Show("Project name is required.", "Validation", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            DialogResult = DialogResult.OK;
        };

        var btnCancel = new Button { Text = "Cancel", Width = 80, Height = 32, Location = new Point(88, 4) };
        ThemeHelper.StyleButton(btnCancel, isPrimary: false);
        btnCancel.Click += (s, e) => DialogResult = DialogResult.Cancel;

        btnPanel.Controls.Add(btnOk);
        btnPanel.Controls.Add(btnCancel);

        Controls.Add(layout);

        AcceptButton = btnOk;
        CancelButton = btnCancel;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private NumericUpDown MakeHoursUpDown()
    {
        var nud = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0,
            Maximum       = 99999,
            DecimalPlaces = 1,
            Increment     = 1m,
            Value         = 0m,
        };
        ThemeHelper.ApplyTheme(nud);
        return nud;
    }

    private NumericUpDown MakeCountUpDown()
    {
        var nud = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0,
            Maximum       = 9999,
            DecimalPlaces = 0,
            Increment     = 1m,
            Value         = 0m,
        };
        ThemeHelper.ApplyTheme(nud);
        return nud;
    }

    private static Label MakeLabel(string text)
    {
        var lbl = new Label { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft };
        ThemeHelper.StyleLabel(lbl);
        return lbl;
    }
}
