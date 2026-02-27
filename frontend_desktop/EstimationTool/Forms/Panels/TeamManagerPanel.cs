using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for managing team members. Supports creating, editing, and
/// deleting team members via the Python IPC backend.
/// </summary>
public class TeamManagerPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class TeamResponse
    {
        [JsonPropertyName("team_members")]
        public List<TeamMember> TeamMembers { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private readonly DataGridView _grid;
    private readonly Button _btnAdd;
    private readonly Button _btnEdit;
    private readonly Button _btnDelete;
    private readonly Label _headerLabel;

    private List<TeamMember> _members = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public TeamManagerPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // --- Header ---
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 48,
        };

        _headerLabel = new Label
        {
            Text = "Team Members",
            AutoSize = true,
            Location = new Point(0, 8),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);
        headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        var toolbar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 40,
        };

        _btnAdd    = new Button { Text = "Add Member", Width = 100, Height = 32, Location = new Point(0,   4) };
        _btnEdit   = new Button { Text = "Edit",       Width = 80,  Height = 32, Location = new Point(106, 4) };
        _btnDelete = new Button { Text = "Delete",     Width = 80,  Height = 32, Location = new Point(192, 4) };

        ThemeHelper.StyleButton(_btnAdd,    isPrimary: true);
        ThemeHelper.StyleButton(_btnEdit,   isPrimary: false);
        ThemeHelper.StyleButton(_btnDelete, isPrimary: false);

        toolbar.Controls.Add(_btnAdd);
        toolbar.Controls.Add(_btnEdit);
        toolbar.Controls.Add(_btnDelete);

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

        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Id",               HeaderText = "ID",                  FillWeight = 8  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Name",             HeaderText = "Name",                FillWeight = 35 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Role",             HeaderText = "Role",                FillWeight = 25 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "AvailableHours",   HeaderText = "Available Hours/Day", FillWeight = 20 });

        // -------------------------------------------------------------------------
        // Layout
        // -------------------------------------------------------------------------
        Controls.Add(_grid);
        Controls.Add(toolbar);
        Controls.Add(headerPanel);

        // -------------------------------------------------------------------------
        // Events
        // -------------------------------------------------------------------------
        _btnAdd.Click    += BtnAdd_Click;
        _btnEdit.Click   += BtnEdit_Click;
        _btnDelete.Click += BtnDelete_Click;
        _grid.CellDoubleClick += (s, e) => { if (e.RowIndex >= 0) OpenEditDialog(GetSelectedMember()); };

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
            var response = await _ipc.SendCommandAsync<TeamResponse>("get_team_members");
            _members = response.TeamMembers;

            _grid.Rows.Clear();
            foreach (var m in _members)
            {
                _grid.Rows.Add(
                    m.Id,
                    m.Name,
                    m.Role,
                    m.AvailableHoursPerDay.ToString("F1"));
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load team members:\n{ex.Message}",
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
        using var dialog = new TeamMemberDialog("Add Team Member");
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_team_member", new
            {
                name                    = dialog.MemberName,
                role                    = dialog.Role,
                available_hours_per_day = dialog.AvailableHoursPerDay,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create team member:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void BtnEdit_Click(object? sender, EventArgs e)
    {
        var member = GetSelectedMember();
        if (member is null)
        {
            MessageBox.Show("Please select a team member to edit.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        OpenEditDialog(member);
    }

    private void OpenEditDialog(TeamMember? member)
    {
        if (member is null) return;

        using var dialog = new TeamMemberDialog("Edit Team Member", member);
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        _ = SaveEditAsync(member.Id, dialog);
    }

    private async Task SaveEditAsync(int id, TeamMemberDialog dialog)
    {
        try
        {
            await _ipc.SendCommandAsync<object>("update_team_member", new
            {
                id,
                name                    = dialog.MemberName,
                role                    = dialog.Role,
                available_hours_per_day = dialog.AvailableHoursPerDay,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to update team member:\n{ex.Message}",
                "Update Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnDelete_Click(object? sender, EventArgs e)
    {
        var member = GetSelectedMember();
        if (member is null)
        {
            MessageBox.Show("Please select a team member to delete.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var confirm = MessageBox.Show(
            $"Delete team member \"{member.Name}\"? This cannot be undone.",
            "Confirm Delete",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning);

        if (confirm != DialogResult.Yes) return;

        try
        {
            await _ipc.SendCommandAsync<object>("delete_team_member", new { id = member.Id });
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to delete team member:\n{ex.Message}",
                "Delete Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private TeamMember? GetSelectedMember()
    {
        if (_grid.CurrentRow is null) return null;
        var id = _grid.CurrentRow.Cells["Id"].Value as int?
                 ?? (int.TryParse(_grid.CurrentRow.Cells["Id"].Value?.ToString(), out var parsed) ? parsed : -1);
        return _members.FirstOrDefault(m => m.Id == id);
    }
}

// =============================================================================
// Team Member Add/Edit dialog
// =============================================================================

sealed class TeamMemberDialog : Form
{
    // Outputs
    public string MemberName          => _txtName.Text.Trim();
    public string Role                => _cmbRole.SelectedItem?.ToString() ?? "TESTER";
    public double AvailableHoursPerDay => (double)_nudHours.Value;

    private readonly TextBox       _txtName;
    private readonly ComboBox      _cmbRole;
    private readonly NumericUpDown _nudHours;

    private static readonly string[] Roles = ["TESTER", "LEADER", "MANAGER"];

    public TeamMemberDialog(string title, TeamMember? existing = null)
    {
        Text            = title;
        Size            = new Size(400, 260);
        MinimumSize     = new Size(360, 240);
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
            RowCount    = 5,
            Padding     = new Padding(16),
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 140));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // Name
        layout.Controls.Add(MakeLabel("Name *"), 0, 0);
        _txtName = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtName);
        layout.Controls.Add(_txtName, 1, 0);

        // Role
        layout.Controls.Add(MakeLabel("Role"), 0, 1);
        _cmbRole = new ComboBox
        {
            Dock          = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
        };
        _cmbRole.Items.AddRange(Roles);
        _cmbRole.SelectedIndex = 0;
        ThemeHelper.StyleComboBox(_cmbRole);
        layout.Controls.Add(_cmbRole, 1, 1);

        // Available hours per day
        layout.Controls.Add(MakeLabel("Available Hours/Day"), 0, 2);
        _nudHours = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0.5m,
            Maximum       = 12.0m,
            DecimalPlaces = 1,
            Increment     = 0.5m,
            Value         = 7.0m,
        };
        ThemeHelper.ApplyTheme(_nudHours);
        layout.Controls.Add(_nudHours, 1, 2);

        // Buttons
        var btnPanel = new Panel { Dock = DockStyle.Fill };
        layout.Controls.Add(new Label(), 0, 3);
        layout.Controls.Add(btnPanel, 1, 3);

        var btnOk = new Button { Text = "Save", Width = 80, Height = 32, Location = new Point(0, 4) };
        ThemeHelper.StyleButton(btnOk, isPrimary: true);
        btnOk.Click += (s, e) =>
        {
            if (string.IsNullOrWhiteSpace(_txtName.Text))
            {
                MessageBox.Show("Name is required.", "Validation", MessageBoxButtons.OK, MessageBoxIcon.Warning);
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

        // Pre-populate for edit mode
        if (existing is not null)
        {
            _txtName.Text     = existing.Name;
            var roleIndex = Array.IndexOf(Roles, existing.Role.ToUpperInvariant());
            _cmbRole.SelectedIndex = roleIndex >= 0 ? roleIndex : 0;
            _nudHours.Value   = (decimal)Math.Clamp(existing.AvailableHoursPerDay, 0.5, 12.0);
        }

        AcceptButton = btnOk;
        CancelButton = btnCancel;
    }

    private static Label MakeLabel(string text)
    {
        var lbl = new Label { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft };
        ThemeHelper.StyleLabel(lbl);
        return lbl;
    }
}
