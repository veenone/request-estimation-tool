using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for managing test profiles. Supports creating, editing, and
/// deleting profiles via the Python IPC backend.
/// </summary>
public partial class ProfileManagerPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class ProfilesResponse
    {
        [JsonPropertyName("profiles")]
        public List<TestProfile> Profiles { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private List<TestProfile> _profiles = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public ProfileManagerPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock    = DockStyle.Fill;
        Padding = new Padding(0);

        InitializeComponent();

        _btnAdd.Click    += BtnAdd_Click;
        _btnEdit.Click   += BtnEdit_Click;
        _btnDelete.Click += BtnDelete_Click;
        _grid.CellDoubleClick += (s, e) => { if (e.RowIndex >= 0) OpenEditDialog(GetSelectedProfile()); };

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
            var response = await _ipc.SendCommandAsync<ProfilesResponse>("get_profiles");
            _profiles = response.Profiles;

            _grid.Rows.Clear();
            foreach (var p in _profiles)
            {
                _grid.Rows.Add(
                    p.Id,
                    p.Name,
                    p.Description ?? "",
                    p.EffortMultiplier.ToString("F2"));
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load profiles:\n{ex.Message}",
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
        using var dialog = new ProfileDialog("Add Test Profile");
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_profile", new
            {
                name              = dialog.ProfileName,
                description       = dialog.Description,
                effort_multiplier = dialog.EffortMultiplier,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create profile:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void BtnEdit_Click(object? sender, EventArgs e)
    {
        var profile = GetSelectedProfile();
        if (profile is null)
        {
            MessageBox.Show("Please select a profile to edit.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        OpenEditDialog(profile);
    }

    private void OpenEditDialog(TestProfile? profile)
    {
        if (profile is null) return;

        using var dialog = new ProfileDialog("Edit Test Profile", profile);
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        _ = SaveEditAsync(profile.Id, dialog);
    }

    private async Task SaveEditAsync(int id, ProfileDialog dialog)
    {
        try
        {
            await _ipc.SendCommandAsync<object>("update_profile", new
            {
                id,
                name              = dialog.ProfileName,
                description       = dialog.Description,
                effort_multiplier = dialog.EffortMultiplier,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to update profile:\n{ex.Message}",
                "Update Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnDelete_Click(object? sender, EventArgs e)
    {
        var profile = GetSelectedProfile();
        if (profile is null)
        {
            MessageBox.Show("Please select a profile to delete.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var confirm = MessageBox.Show(
            $"Delete profile \"{profile.Name}\"? This cannot be undone.",
            "Confirm Delete",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning);

        if (confirm != DialogResult.Yes) return;

        try
        {
            await _ipc.SendCommandAsync<object>("delete_profile", new { id = profile.Id });
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to delete profile:\n{ex.Message}",
                "Delete Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private TestProfile? GetSelectedProfile()
    {
        if (_grid.CurrentRow is null) return null;
        var id = _grid.CurrentRow.Cells["Id"].Value as int?
                 ?? (int.TryParse(_grid.CurrentRow.Cells["Id"].Value?.ToString(), out var parsed) ? parsed : -1);
        return _profiles.FirstOrDefault(p => p.Id == id);
    }
}

// =============================================================================
// Profile Add/Edit dialog
// =============================================================================

sealed class ProfileDialog : Form
{
    // Outputs
    public string ProfileName      => _txtName.Text.Trim();
    public string Description      => _txtDescription.Text.Trim();
    public double EffortMultiplier => (double)_nudMultiplier.Value;

    private readonly TextBox       _txtName;
    private readonly TextBox       _txtDescription;
    private readonly NumericUpDown _nudMultiplier;

    public ProfileDialog(string title, TestProfile? existing = null)
    {
        Text            = title;
        Size            = new Size(420, 310);
        MinimumSize     = new Size(380, 290);
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

        // Description
        layout.Controls.Add(MakeLabel("Description"), 0, 1);
        _txtDescription = new TextBox
        {
            Dock       = DockStyle.Fill,
            Multiline  = true,
            Height     = 60,
            ScrollBars = ScrollBars.Vertical,
        };
        ThemeHelper.StyleTextBox(_txtDescription);
        layout.Controls.Add(_txtDescription, 1, 1);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 70));

        // Effort multiplier
        layout.Controls.Add(MakeLabel("Effort Multiplier"), 0, 2);
        _nudMultiplier = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0.1m,
            Maximum       = 10.0m,
            DecimalPlaces = 2,
            Increment     = 0.1m,
            Value         = 1.0m,
        };
        ThemeHelper.ApplyTheme(_nudMultiplier);
        layout.Controls.Add(_nudMultiplier, 1, 2);

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
            _txtName.Text        = existing.Name;
            _txtDescription.Text = existing.Description ?? "";
            _nudMultiplier.Value = (decimal)Math.Clamp(existing.EffortMultiplier, 0.1, 10.0);
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
