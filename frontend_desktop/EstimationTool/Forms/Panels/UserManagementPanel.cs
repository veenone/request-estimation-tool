using System.Text.Json.Serialization;
using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for managing application users. Only accessible to ADMIN users.
/// Supports creating, editing, and deleting users via the backend API.
/// </summary>
public partial class UserManagementPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper & model
    // -------------------------------------------------------------------------

    private sealed class UsersResponse
    {
        [JsonPropertyName("users")]
        public List<UserRecord> Users { get; set; } = new();
    }

    private sealed class UserRecord
    {
        [JsonPropertyName("id")]           public int     Id          { get; set; }
        [JsonPropertyName("username")]     public string  Username    { get; set; } = "";
        [JsonPropertyName("display_name")] public string  DisplayName { get; set; } = "";
        [JsonPropertyName("email")]        public string  Email       { get; set; } = "";
        [JsonPropertyName("role")]         public string  Role        { get; set; } = "";
        [JsonPropertyName("is_active")]    public bool    IsActive    { get; set; } = true;
        [JsonPropertyName("last_login")]   public string? LastLogin   { get; set; }
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly string _authToken;

    private List<UserRecord> _users = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public UserManagementPanel(BackendApiService ipc, string authToken)
    {
        _ipc       = ipc;
        _authToken = authToken;

        Dock    = DockStyle.Fill;
        Padding = new Padding(0);

        InitializeComponent();

        _btnAdd.Click    += BtnAdd_Click;
        _btnEdit.Click   += BtnEdit_Click;
        _btnDelete.Click += BtnDelete_Click;
        _grid.CellDoubleClick += (s, e) => { if (e.RowIndex >= 0) OpenEditDialog(GetSelectedUser()); };

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
            var response = await _ipc.SendCommandAsync<UsersResponse>("get_users", new
            {
                token = _authToken,
            });
            _users = response.Users;

            _grid.Rows.Clear();
            foreach (var u in _users)
            {
                _grid.Rows.Add(
                    u.Id,
                    u.Username,
                    u.DisplayName,
                    u.Email,
                    u.Role,
                    u.IsActive ? "Yes" : "No",
                    u.LastLogin ?? "Never");
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load users:\n{ex.Message}",
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
        using var dialog = new UserDialog("Add User");
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_user", new
            {
                token        = _authToken,
                username     = dialog.UserName,
                display_name = dialog.UserDisplayName,
                email        = dialog.UserEmail,
                role         = dialog.UserRole,
                password     = dialog.UserPassword,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create user:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void BtnEdit_Click(object? sender, EventArgs e)
    {
        var user = GetSelectedUser();
        if (user is null)
        {
            MessageBox.Show("Please select a user to edit.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        OpenEditDialog(user);
    }

    private void OpenEditDialog(UserRecord? user)
    {
        if (user is null) return;

        using var dialog = new UserDialog("Edit User", user.Username, user.DisplayName, user.Email, user.Role, user.IsActive);
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        _ = SaveEditAsync(user.Id, dialog);
    }

    private async Task SaveEditAsync(int id, UserDialog dialog)
    {
        try
        {
            var payload = new Dictionary<string, object?>
            {
                ["token"]        = _authToken,
                ["id"]           = id,
                ["display_name"] = dialog.UserDisplayName,
                ["email"]        = dialog.UserEmail,
                ["role"]         = dialog.UserRole,
                ["is_active"]    = dialog.UserIsActive,
            };

            // Only include password if it was changed
            if (!string.IsNullOrEmpty(dialog.UserPassword))
            {
                payload["password"] = dialog.UserPassword;
            }

            await _ipc.SendCommandAsync<object>("update_user", payload);
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to update user:\n{ex.Message}",
                "Update Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnDelete_Click(object? sender, EventArgs e)
    {
        var user = GetSelectedUser();
        if (user is null)
        {
            MessageBox.Show("Please select a user to delete.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var confirm = MessageBox.Show(
            $"Delete user \"{user.Username}\"? This cannot be undone.",
            "Confirm Delete",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning);

        if (confirm != DialogResult.Yes) return;

        try
        {
            await _ipc.SendCommandAsync<object>("delete_user", new
            {
                token = _authToken,
                id    = user.Id,
            });
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to delete user:\n{ex.Message}",
                "Delete Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private UserRecord? GetSelectedUser()
    {
        if (_grid.CurrentRow is null) return null;
        var id = _grid.CurrentRow.Cells["Id"].Value as int?
                 ?? (int.TryParse(_grid.CurrentRow.Cells["Id"].Value?.ToString(), out var parsed) ? parsed : -1);
        return _users.FirstOrDefault(u => u.Id == id);
    }
}

// =============================================================================
// User Add/Edit dialog
// =============================================================================

sealed class UserDialog : Form
{
    // Outputs
    public string UserName        => _txtUsername.Text.Trim();
    public string UserDisplayName => _txtDisplayName.Text.Trim();
    public string UserEmail       => _txtEmail.Text.Trim();
    public string UserRole        => _cmbRole.SelectedItem?.ToString() ?? "VIEWER";
    public string UserPassword    => _txtPassword.Text;
    public bool   UserIsActive    => _chkActive.Checked;

    private readonly TextBox  _txtUsername;
    private readonly TextBox  _txtDisplayName;
    private readonly TextBox  _txtEmail;
    private readonly ComboBox _cmbRole;
    private readonly TextBox  _txtPassword;
    private readonly CheckBox _chkActive;
    private readonly bool     _isEditMode;

    private static readonly string[] Roles = ["VIEWER", "ESTIMATOR", "APPROVER", "ADMIN"];

    public UserDialog(
        string title,
        string? existingUsername    = null,
        string? existingDisplayName = null,
        string? existingEmail       = null,
        string? existingRole        = null,
        bool    existingIsActive    = true)
    {
        _isEditMode = existingUsername is not null;

        Text            = title;
        Size            = new Size(460, 380);
        MinimumSize     = new Size(440, 360);
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
            RowCount    = 8,
            Padding     = new Padding(16),
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 120));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // Username
        layout.Controls.Add(MakeLabel("Username *"), 0, 0);
        _txtUsername = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtUsername);
        if (_isEditMode)
        {
            _txtUsername.Text    = existingUsername;
            _txtUsername.Enabled = false;  // Username cannot be changed
        }
        layout.Controls.Add(_txtUsername, 1, 0);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Display Name
        layout.Controls.Add(MakeLabel("Display Name"), 0, 1);
        _txtDisplayName = new TextBox { Dock = DockStyle.Fill, Text = existingDisplayName ?? "" };
        ThemeHelper.StyleTextBox(_txtDisplayName);
        layout.Controls.Add(_txtDisplayName, 1, 1);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Email
        layout.Controls.Add(MakeLabel("Email"), 0, 2);
        _txtEmail = new TextBox { Dock = DockStyle.Fill, Text = existingEmail ?? "" };
        ThemeHelper.StyleTextBox(_txtEmail);
        layout.Controls.Add(_txtEmail, 1, 2);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Role
        layout.Controls.Add(MakeLabel("Role"), 0, 3);
        _cmbRole = new ComboBox
        {
            Dock          = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
        };
        _cmbRole.Items.AddRange(Roles);
        var roleIndex = existingRole is not null
            ? Array.IndexOf(Roles, existingRole.ToUpperInvariant())
            : 0;
        _cmbRole.SelectedIndex = roleIndex >= 0 ? roleIndex : 0;
        ThemeHelper.StyleComboBox(_cmbRole);
        layout.Controls.Add(_cmbRole, 1, 3);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Password
        var passwordLabel = _isEditMode ? "New Password" : "Password *";
        layout.Controls.Add(MakeLabel(passwordLabel), 0, 4);
        _txtPassword = new TextBox
        {
            Dock                 = DockStyle.Fill,
            UseSystemPasswordChar = true,
        };
        ThemeHelper.StyleTextBox(_txtPassword);
        layout.Controls.Add(_txtPassword, 1, 4);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Active checkbox (only shown in edit mode)
        _chkActive = new CheckBox
        {
            Text      = "User is active",
            Dock      = DockStyle.Fill,
            Checked   = existingIsActive,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
        };
        if (_isEditMode)
        {
            layout.Controls.Add(new Label { BackColor = Color.Transparent }, 0, 5);
            layout.Controls.Add(_chkActive, 1, 5);
        }
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));

        // Buttons
        var btnPanel = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };

        var btnOk = new Button { Text = "Save", Width = 80, Height = 32, Location = new Point(0, 4) };
        ThemeHelper.StyleButton(btnOk, isPrimary: true);
        btnOk.Click += (s, e) =>
        {
            if (string.IsNullOrWhiteSpace(_txtUsername.Text))
            {
                MessageBox.Show("Username is required.", "Validation",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (!_isEditMode && string.IsNullOrEmpty(_txtPassword.Text))
            {
                MessageBox.Show("Password is required for new users.", "Validation",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            DialogResult = DialogResult.OK;
        };

        var btnCancel = new Button { Text = "Cancel", Width = 80, Height = 32, Location = new Point(88, 4) };
        ThemeHelper.StyleButton(btnCancel, isPrimary: false);
        btnCancel.Click += (s, e) => DialogResult = DialogResult.Cancel;

        btnPanel.Controls.Add(btnOk);
        btnPanel.Controls.Add(btnCancel);
        layout.Controls.Add(new Label { BackColor = Color.Transparent }, 0, 6);
        layout.Controls.Add(btnPanel, 1, 6);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));

        // Spacer
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        Controls.Add(layout);

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
