using System.Text.Json;
using System.Text.Json.Serialization;
using EstimationTool.Services;

namespace EstimationTool.Forms;

/// <summary>
/// Modal login dialog. Authenticates against the backend via the
/// <see cref="BackendApiService"/> and exposes the returned token and
/// user info on successful login.
/// </summary>
public sealed class LoginForm : Form
{
    // -------------------------------------------------------------------------
    // IPC response DTOs
    // -------------------------------------------------------------------------

    private sealed class LoginResponse
    {
        [JsonPropertyName("token")]        public string Token       { get; set; } = "";
        [JsonPropertyName("user_id")]      public int    UserId      { get; set; }
        [JsonPropertyName("username")]     public string Username    { get; set; } = "";
        [JsonPropertyName("display_name")] public string DisplayName { get; set; } = "";
        [JsonPropertyName("role")]         public string Role        { get; set; } = "";
    }

    // -------------------------------------------------------------------------
    // Public properties — available after DialogResult.OK
    // -------------------------------------------------------------------------

    /// <summary>JWT or session token returned by the backend.</summary>
    public string AuthToken   { get; private set; } = "";

    /// <summary>Numeric user ID.</summary>
    public int    UserId      { get; private set; }

    /// <summary>Login username.</summary>
    public string Username    { get; private set; } = "";

    /// <summary>Human-readable display name.</summary>
    public string DisplayName { get; private set; } = "";

    /// <summary>User role (VIEWER, ESTIMATOR, APPROVER, ADMIN).</summary>
    public string UserRole    { get; private set; } = "";

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private readonly TextBox _txtUsername;
    private readonly TextBox _txtPassword;
    private readonly Button  _btnLogin;
    private readonly Button  _btnCancel;
    private readonly Label   _lblError;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public LoginForm(BackendApiService ipcService)
    {
        _ipc = ipcService;

        Text            = "Login - Estimation Tool";
        Size            = new Size(420, 310);
        MinimumSize     = new Size(400, 290);
        StartPosition   = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false;
        MinimizeBox     = false;
        BackColor       = ThemeHelper.Background;
        ForeColor       = ThemeHelper.Text;
        Font            = new Font("Segoe UI", 9.5f);

        // --- Layout ---
        var layout = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            ColumnCount = 2,
            RowCount    = 6,
            Padding     = new Padding(24),
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // Row 0: Title
        var lblTitle = new Label
        {
            Text      = "Sign In",
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        ThemeHelper.StyleLabel(lblTitle, isHeader: true);
        layout.Controls.Add(lblTitle, 0, 0);
        layout.SetColumnSpan(lblTitle, 2);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));

        // Row 1: Username
        layout.Controls.Add(MakeLabel("Username"), 0, 1);
        _txtUsername = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtUsername);
        layout.Controls.Add(_txtUsername, 1, 1);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Row 2: Password
        layout.Controls.Add(MakeLabel("Password"), 0, 2);
        _txtPassword = new TextBox
        {
            Dock         = DockStyle.Fill,
            UseSystemPasswordChar = true,
        };
        ThemeHelper.StyleTextBox(_txtPassword);
        layout.Controls.Add(_txtPassword, 1, 2);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

        // Row 3: Error label
        _lblError = new Label
        {
            Text      = "",
            Dock      = DockStyle.Fill,
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize  = false,
            Visible   = false,
        };
        layout.Controls.Add(_lblError, 0, 3);
        layout.SetColumnSpan(_lblError, 2);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));

        // Row 4: Buttons
        var btnPanel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
        };

        _btnLogin = new Button
        {
            Text     = "Login",
            Width    = 90,
            Height   = 34,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleButton(_btnLogin, isPrimary: true);
        _btnLogin.Click += BtnLogin_Click;

        _btnCancel = new Button
        {
            Text     = "Cancel",
            Width    = 90,
            Height   = 34,
            Location = new Point(98, 4),
        };
        ThemeHelper.StyleButton(_btnCancel, isPrimary: false);
        _btnCancel.Click += (s, e) => { DialogResult = DialogResult.Cancel; };

        btnPanel.Controls.Add(_btnLogin);
        btnPanel.Controls.Add(_btnCancel);
        layout.Controls.Add(new Label { BackColor = Color.Transparent }, 0, 4);
        layout.Controls.Add(btnPanel, 1, 4);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));

        // Row 5: Spacer
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        Controls.Add(layout);

        AcceptButton = _btnLogin;
        CancelButton = _btnCancel;
    }

    // -------------------------------------------------------------------------
    // Login handler
    // -------------------------------------------------------------------------

    private async void BtnLogin_Click(object? sender, EventArgs e)
    {
        var username = _txtUsername.Text.Trim();
        var password = _txtPassword.Text;

        if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password))
        {
            ShowError("Username and password are required.");
            return;
        }

        _btnLogin.Enabled = false;
        _btnLogin.Text    = "Logging in...";
        _lblError.Visible = false;

        try
        {
            var response = await _ipc.SendCommandAsync<LoginResponse>("login", new
            {
                username,
                password,
            });

            AuthToken   = response.Token;
            UserId      = response.UserId;
            Username    = response.Username;
            DisplayName = string.IsNullOrEmpty(response.DisplayName) ? response.Username : response.DisplayName;
            UserRole    = response.Role;

            DialogResult = DialogResult.OK;
        }
        catch (Exception ex)
        {
            ShowError(ex.Message.Contains("401") || ex.Message.Contains("nauthorized")
                ? "Invalid username or password."
                : $"Login failed: {ex.Message}");
        }
        finally
        {
            _btnLogin.Enabled = true;
            _btnLogin.Text    = "Login";
        }
    }

    private void ShowError(string message)
    {
        _lblError.Text    = message;
        _lblError.Visible = true;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Label MakeLabel(string text)
    {
        var lbl = new Label
        {
            Text      = text,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        ThemeHelper.StyleLabel(lbl);
        return lbl;
    }
}
