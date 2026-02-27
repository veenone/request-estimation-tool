using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step4DutProfile : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrappers
    // -------------------------------------------------------------------------

    private class DutTypesResponse
    {
        [JsonPropertyName("dut_types")] public List<DutType> DutTypes { get; set; } = new();
    }

    private class ProfilesResponse
    {
        [JsonPropertyName("profiles")] public List<TestProfile> Profiles { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly WizardPanel.WizardState _state;

    private List<DutType> _duts = new();
    private List<TestProfile> _profiles = new();

    private CheckedListBox _clbDuts     = null!;
    private CheckedListBox _clbProfiles = null!;
    private DataGridView   _dgvMatrix   = null!;

    private Label _lblLoading = null!;
    private Label _lblSummary = null!;

    // Track checkbox suppress re-entrancy
    private bool _suppressMatrixRebuild;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step4DutProfile(BackendApiService ipc, WizardPanel.WizardState state)
    {
        _ipc   = ipc;
        _state = state;

        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        BuildUI();
        Load += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // UI construction
    // -------------------------------------------------------------------------

    private void BuildUI()
    {
        var outerLayout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 4,
            ColumnCount = 1,
            BackColor = ThemeHelper.Background,
        };
        outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));  // header
        outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 200)); // selections
        outerLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));  // matrix
        outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));  // summary/loading
        outerLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(outerLayout);

        // Header
        var lblHeader = new Label
        {
            Text = "Step 4: DUT x Profile Matrix",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        outerLayout.Controls.Add(lblHeader, 0, 0);

        // Selections row: DUTs left, Profiles right
        var selectionPanel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = ThemeHelper.Background,
        };
        selectionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        selectionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        selectionPanel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        // DUT panel
        var dutPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 0, 8, 0),
        };
        var lblDuts = new Label
        {
            Text = "DUT Types (select all that apply) *",
            Font = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            Height = 22,
        };
        _clbDuts = new CheckedListBox
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            CheckOnClick = true,
            Font = new Font("Segoe UI", 9f),
        };
        dutPanel.Controls.Add(_clbDuts);
        dutPanel.Controls.Add(lblDuts);
        selectionPanel.Controls.Add(dutPanel, 0, 0);

        // Profile panel
        var profilePanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(8, 0, 0, 0),
        };
        var lblProfiles = new Label
        {
            Text = "Test Profiles (select all that apply) *",
            Font = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            Height = 22,
        };
        _clbProfiles = new CheckedListBox
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            CheckOnClick = true,
            Font = new Font("Segoe UI", 9f),
        };
        profilePanel.Controls.Add(_clbProfiles);
        profilePanel.Controls.Add(lblProfiles);
        selectionPanel.Controls.Add(profilePanel, 1, 0);

        outerLayout.Controls.Add(selectionPanel, 0, 1);

        // Matrix panel
        var matrixContainer = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
        };

        var lblMatrix = new Label
        {
            Text = "Test Matrix — uncheck combinations you do NOT need to test:",
            Font = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            Height = 22,
        };

        _dgvMatrix = new DataGridView
        {
            Dock = DockStyle.Fill,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_dgvMatrix);
        _dgvMatrix.ReadOnly = false;
        _dgvMatrix.EditMode = DataGridViewEditMode.EditOnKeystrokeOrF2;
        _dgvMatrix.RowHeadersVisible = true;
        _dgvMatrix.RowHeadersWidth = 140;
        _dgvMatrix.RowHeadersDefaultCellStyle.BackColor = ThemeHelper.Sidebar;
        _dgvMatrix.RowHeadersDefaultCellStyle.ForeColor = ThemeHelper.TextSecondary;
        _dgvMatrix.RowHeadersDefaultCellStyle.Font = new Font("Segoe UI", 8.5f);
        _dgvMatrix.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.AllCells;

        _dgvMatrix.CellValueChanged += DgvMatrix_CellValueChanged;
        _dgvMatrix.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_dgvMatrix.IsCurrentCellDirty)
                _dgvMatrix.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };

        matrixContainer.Controls.Add(_dgvMatrix);
        matrixContainer.Controls.Add(lblMatrix);

        outerLayout.Controls.Add(matrixContainer, 0, 2);

        // Summary/loading row
        var bottomPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
        };

        _lblSummary = new Label
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.Accent,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };

        _lblLoading = new Label
        {
            Text = "Loading DUT types and profiles...",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };

        bottomPanel.Controls.Add(_lblSummary);
        bottomPanel.Controls.Add(_lblLoading);

        outerLayout.Controls.Add(bottomPanel, 0, 3);

        // Wire up selection-change events
        _clbDuts.ItemCheck    += ClbItemCheck;
        _clbProfiles.ItemCheck += ClbItemCheck;
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var dutsTask     = _ipc.SendCommandAsync<DutTypesResponse>("get_dut_types");
            var profilesTask = _ipc.SendCommandAsync<ProfilesResponse>("get_profiles");
            await Task.WhenAll(dutsTask, profilesTask);

            _duts     = dutsTask.Result.DutTypes;
            _profiles = profilesTask.Result.Profiles;

            if (InvokeRequired)
                BeginInvoke(PopulateLists);
            else
                PopulateLists();
        }
        catch (Exception ex)
        {
            if (InvokeRequired)
                BeginInvoke(() =>
                {
                    _lblLoading.Text = $"Error loading data: {ex.Message}";
                    _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
                });
            else
            {
                _lblLoading.Text = $"Error loading data: {ex.Message}";
                _lblLoading.ForeColor = ThemeHelper.FeasibilityRed;
            }
        }
    }

    private void PopulateLists()
    {
        _suppressMatrixRebuild = true;

        _clbDuts.Items.Clear();
        foreach (var dut in _duts)
        {
            bool isChecked = _state.SelectedDutIds.Contains(dut.Id);
            _clbDuts.Items.Add(new DutItem(dut), isChecked);
        }

        _clbProfiles.Items.Clear();
        foreach (var profile in _profiles)
        {
            bool isChecked = _state.SelectedProfileIds.Contains(profile.Id);
            _clbProfiles.Items.Add(new ProfileItem(profile), isChecked);
        }

        _suppressMatrixRebuild = false;

        _lblLoading.Text = "";
        RebuildMatrix();
    }

    // -------------------------------------------------------------------------
    // Matrix building
    // -------------------------------------------------------------------------

    private void RebuildMatrix()
    {
        var selectedDuts     = GetSelectedDuts();
        var selectedProfiles = GetSelectedProfiles();

        _dgvMatrix.Columns.Clear();
        _dgvMatrix.Rows.Clear();

        if (selectedDuts.Count == 0 || selectedProfiles.Count == 0)
        {
            UpdateSummary(0, 0, 0);
            return;
        }

        // Add one checkbox column per profile
        foreach (var profile in selectedProfiles)
        {
            var col = new DataGridViewCheckBoxColumn
            {
                HeaderText = profile.Name,
                Name = $"Profile_{profile.Id}",
                Tag = profile,
                Width = Math.Max(70, profile.Name.Length * 7 + 20),
                AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
                Resizable = DataGridViewTriState.False,
                ToolTipText = $"Multiplier: {profile.EffortMultiplier:F1}x" +
                              (profile.Description != null ? $"\n{profile.Description}" : ""),
            };
            _dgvMatrix.Columns.Add(col);
        }

        // Add one row per DUT
        bool hasPreviousMatrix = _state.DutProfileMatrix.Count > 0;

        foreach (var dut in selectedDuts)
        {
            int rowIdx = _dgvMatrix.Rows.Add();
            _dgvMatrix.Rows[rowIdx].HeaderCell.Value = dut.Name;
            _dgvMatrix.Rows[rowIdx].Tag = dut;

            foreach (DataGridViewCheckBoxColumn col in _dgvMatrix.Columns)
            {
                var profile = (TestProfile)col.Tag!;

                // Determine initial checked state
                bool shouldCheck;
                if (hasPreviousMatrix)
                {
                    // Restore from prior state
                    shouldCheck = _state.DutProfileMatrix.Any(
                        pair => pair.Count >= 2 && pair[0] == dut.Id && pair[1] == profile.Id);
                }
                else
                {
                    // Default: all combinations checked
                    shouldCheck = true;
                }

                _dgvMatrix.Rows[rowIdx].Cells[col.Index].Value = shouldCheck;
            }
        }

        UpdateSummaryFromGrid();
    }

    private void UpdateSummaryFromGrid()
    {
        int dutCount     = _dgvMatrix.Rows.Count;
        int profileCount = _dgvMatrix.Columns.Count;

        int checkedCount = 0;
        foreach (DataGridViewRow row in _dgvMatrix.Rows)
            foreach (DataGridViewColumn col in _dgvMatrix.Columns)
                if (Convert.ToBoolean(row.Cells[col.Index].Value))
                    checkedCount++;

        UpdateSummary(dutCount, profileCount, checkedCount);
    }

    private void UpdateSummary(int dutCount, int profileCount, int combinations)
    {
        if (dutCount == 0 || profileCount == 0)
        {
            _lblSummary.Text = "Select at least one DUT and one profile to build the matrix.";
            _lblSummary.ForeColor = ThemeHelper.TextSecondary;
        }
        else
        {
            int possible = dutCount * profileCount;
            _lblSummary.Text = $"{dutCount} DUT(s)  x  {profileCount} profile(s)  =  {possible} possible  |  " +
                               $"{combinations} combination(s) selected for testing";

            _lblSummary.ForeColor = combinations > 20
                ? ThemeHelper.FeasibilityAmber
                : ThemeHelper.Accent;
        }
    }

    // -------------------------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------------------------

    private void ClbItemCheck(object? sender, ItemCheckEventArgs e)
    {
        // ItemCheck fires before the check state changes; we post-invoke so the
        // list's checked state is already updated when we rebuild.
        BeginInvoke(() =>
        {
            if (!_suppressMatrixRebuild)
                RebuildMatrix();
        });
    }

    private void DgvMatrix_CellValueChanged(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0) return;
        UpdateSummaryFromGrid();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private List<DutType> GetSelectedDuts()
    {
        var result = new List<DutType>();
        for (int i = 0; i < _clbDuts.Items.Count; i++)
            if (_clbDuts.GetItemChecked(i) && _clbDuts.Items[i] is DutItem di)
                result.Add(di.Dut);
        return result;
    }

    private List<TestProfile> GetSelectedProfiles()
    {
        var result = new List<TestProfile>();
        for (int i = 0; i < _clbProfiles.Items.Count; i++)
            if (_clbProfiles.GetItemChecked(i) && _clbProfiles.Items[i] is ProfileItem pi)
                result.Add(pi.Profile);
        return result;
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public bool Validate(out string error)
    {
        if (GetSelectedDuts().Count == 0)
        {
            error = "Please select at least one DUT type.";
            return false;
        }
        if (GetSelectedProfiles().Count == 0)
        {
            error = "Please select at least one test profile.";
            return false;
        }

        bool anyChecked = false;
        foreach (DataGridViewRow row in _dgvMatrix.Rows)
            foreach (DataGridViewColumn col in _dgvMatrix.Columns)
                if (Convert.ToBoolean(row.Cells[col.Index].Value))
                { anyChecked = true; break; }

        if (!anyChecked)
        {
            error = "At least one DUT/Profile combination must be selected in the matrix.";
            return false;
        }

        error = "";
        return true;
    }

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.SelectedDutIds.Clear();
        state.SelectedProfileIds.Clear();
        state.DutProfileMatrix.Clear();

        state.SelectedDutIds.AddRange(GetSelectedDuts().Select(d => d.Id));
        state.SelectedProfileIds.AddRange(GetSelectedProfiles().Select(p => p.Id));

        foreach (DataGridViewRow row in _dgvMatrix.Rows)
        {
            if (row.Tag is not DutType dut) continue;
            foreach (DataGridViewColumn col in _dgvMatrix.Columns)
            {
                if (col.Tag is not TestProfile profile) continue;
                if (Convert.ToBoolean(row.Cells[col.Index].Value))
                    state.DutProfileMatrix.Add(new List<int> { dut.Id, profile.Id });
            }
        }
    }

    // -------------------------------------------------------------------------
    // List item wrappers
    // -------------------------------------------------------------------------

    private sealed class DutItem(DutType dut)
    {
        public DutType Dut { get; } = dut;
        public override string ToString() => $"{Dut.Name}  ({Dut.ComplexityMultiplier:F1}x)";
    }

    private sealed class ProfileItem(TestProfile profile)
    {
        public TestProfile Profile { get; } = profile;
        public override string ToString() => $"{Profile.Name}  ({Profile.EffortMultiplier:F1}x)";
    }
}
