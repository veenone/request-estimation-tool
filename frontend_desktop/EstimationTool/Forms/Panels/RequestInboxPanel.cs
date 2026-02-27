using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Request Inbox panel — lists all incoming test requests with filtering, inline
/// CRUD, and navigation to the estimation wizard. All UI built programmatically.
/// </summary>
public sealed class RequestInboxPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Private IPC response wrapper
    // -------------------------------------------------------------------------

    private class RequestsResponse
    {
        [JsonPropertyName("requests")]
        public List<Request> Requests { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly MainForm _mainForm;

    private DataGridView _dgv = null!;
    private ComboBox _cmbStatusFilter = null!;
    private Button _btnCreateEstimation = null!;
    private Button _btnEdit = null!;
    private Button _btnViewDetails = null!;
    private Button _btnAddRequest = null!;
    private Button _btnRefresh = null!;
    private Label _lblStatus = null!;

    private List<Request> _rows = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public RequestInboxPanel(BackendApiService ipc, MainForm mainForm)
    {
        _ipc = ipc;
        _mainForm = mainForm;

        BackColor = ThemeHelper.Background;
        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        BuildLayout();
        UpdateButtonStates();

        HandleCreated += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    private void BuildLayout()
    {
        var stack = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            ColumnCount = 1,
            RowCount = 5,
            Padding = new Padding(0),
        };
        stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));   // Header
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));   // Toolbar
        stack.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));  // Grid
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));   // Bottom action bar
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));   // Status bar
        Controls.Add(stack);

        stack.Controls.Add(BuildHeader(), 0, 0);
        stack.Controls.Add(BuildToolbar(), 0, 1);
        stack.Controls.Add(BuildGrid(), 0, 2);
        stack.Controls.Add(BuildActionBar(), 0, 3);
        stack.Controls.Add(BuildStatusBar(), 0, 4);
    }

    private static Panel BuildHeader()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 0, 0, 8),
        };
        panel.Controls.Add(new Label
        {
            Text = "Request Inbox",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        });
        return panel;
    }

    private Panel BuildToolbar()
    {
        var bar = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 4, 0, 4),
        };

        // Filter label
        var lblFilter = new Label
        {
            Text = "Status:",
            AutoSize = true,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        lblFilter.Location = new Point(0, 10);
        bar.Controls.Add(lblFilter);

        // Status filter combo
        _cmbStatusFilter = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Width = 160,
        };
        _cmbStatusFilter.Items.AddRange(new object[]
        {
            "All", "NEW", "IN_ESTIMATION", "ESTIMATED", "COMPLETED"
        });
        _cmbStatusFilter.SelectedIndex = 0;
        ThemeHelper.StyleComboBox(_cmbStatusFilter);
        _cmbStatusFilter.Location = new Point(lblFilter.Left + 48, 6);
        _cmbStatusFilter.SelectedIndexChanged += async (_, _) => await LoadDataAsync();
        bar.Controls.Add(_cmbStatusFilter);

        // Add Request button
        _btnAddRequest = new Button
        {
            Text = "+ Add Request",
            Width = 120,
            Height = 30,
        };
        ThemeHelper.StyleButton(_btnAddRequest, isPrimary: true);
        _btnAddRequest.Location = new Point(_cmbStatusFilter.Right + 16, 6);
        _btnAddRequest.Click += BtnAddRequest_Click;
        bar.Controls.Add(_btnAddRequest);

        // Refresh button
        _btnRefresh = new Button
        {
            Text = "Refresh",
            Width = 90,
            Height = 30,
        };
        ThemeHelper.StyleButton(_btnRefresh, isPrimary: false);
        _btnRefresh.Location = new Point(_btnAddRequest.Right + 8, 6);
        _btnRefresh.Click += async (_, _) => await LoadDataAsync();
        bar.Controls.Add(_btnRefresh);

        return bar;
    }

    private Panel BuildGrid()
    {
        var container = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(1),
        };

        _dgv = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            MultiSelect = false,
        };

        ThemeHelper.StyleDataGridView(_dgv);

        _dgv.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColNum",      HeaderText = "Number",        FillWeight = 12 },
            new DataGridViewTextBoxColumn { Name = "ColTitle",    HeaderText = "Title",          FillWeight = 22 },
            new DataGridViewTextBoxColumn { Name = "ColRequester",HeaderText = "Requester",      FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColPriority", HeaderText = "Priority",       FillWeight = 10 },
            new DataGridViewTextBoxColumn { Name = "ColStatus",   HeaderText = "Status",         FillWeight = 12 },
            new DataGridViewTextBoxColumn { Name = "ColBU",       HeaderText = "Business Unit",  FillWeight = 12 },
            new DataGridViewTextBoxColumn { Name = "ColReceived", HeaderText = "Received",       FillWeight = 10 },
            new DataGridViewTextBoxColumn { Name = "ColDelivery", HeaderText = "Delivery",       FillWeight = 10 }
        );

        _dgv.SelectionChanged += Dgv_SelectionChanged;
        _dgv.CellFormatting += Dgv_CellFormatting;
        _dgv.CellDoubleClick += Dgv_CellDoubleClick;

        container.Controls.Add(_dgv);
        return container;
    }

    private Panel BuildActionBar()
    {
        var bar = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 8, 0, 4),
        };

        _btnCreateEstimation = new Button
        {
            Text = "Create Estimation",
            Width = 160,
            Height = 30,
            Enabled = false,
        };
        ThemeHelper.StyleButton(_btnCreateEstimation, isPrimary: true);
        _btnCreateEstimation.Location = new Point(0, 6);
        _btnCreateEstimation.Click += BtnCreateEstimation_Click;
        bar.Controls.Add(_btnCreateEstimation);

        _btnEdit = new Button
        {
            Text = "Edit",
            Width = 90,
            Height = 30,
            Enabled = false,
        };
        ThemeHelper.StyleButton(_btnEdit, isPrimary: false);
        _btnEdit.Location = new Point(_btnCreateEstimation.Right + 8, 6);
        _btnEdit.Click += BtnEdit_Click;
        bar.Controls.Add(_btnEdit);

        _btnViewDetails = new Button
        {
            Text = "View Details",
            Width = 110,
            Height = 30,
            Enabled = false,
        };
        ThemeHelper.StyleButton(_btnViewDetails, isPrimary: false);
        _btnViewDetails.Location = new Point(_btnEdit.Right + 8, 6);
        _btnViewDetails.Click += BtnViewDetails_Click;
        bar.Controls.Add(_btnViewDetails);

        return bar;
    }

    private Panel BuildStatusBar()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
        };

        _lblStatus = new Label
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Text = "Loading...",
        };
        panel.Controls.Add(_lblStatus);
        return panel;
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        SetStatus("Loading...", ThemeHelper.TextSecondary);

        try
        {
            string? selectedStatus = _cmbStatusFilter.SelectedItem?.ToString();
            bool filterAll = string.IsNullOrEmpty(selectedStatus) || selectedStatus == "All";

            RequestsResponse response;
            if (filterAll)
            {
                response = await _ipc.SendCommandAsync<RequestsResponse>("get_requests");
            }
            else
            {
                response = await _ipc.SendCommandAsync<RequestsResponse>(
                    "get_requests",
                    new { status = selectedStatus });
            }

            PopulateGrid(response.Requests);
            SetStatus($"{response.Requests.Count} request(s) loaded.", ThemeHelper.TextSecondary);
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            SetStatus($"Error: {ex.Message}", ThemeHelper.FeasibilityRed);
        }
    }

    private void PopulateGrid(List<Request> requests)
    {
        Action populate = () =>
        {
            if (IsDisposed) return;

            _rows = requests;
            _dgv.Rows.Clear();

            foreach (var r in _rows)
            {
                _dgv.Rows.Add(
                    r.RequestNumber,
                    r.Title,
                    r.RequesterName,
                    r.Priority,
                    r.Status,
                    r.BusinessUnit ?? "",
                    FormatDate(r.ReceivedDate),
                    FormatDate(r.RequestedDeliveryDate)
                );
            }

            UpdateButtonStates();
        };

        if (InvokeRequired)
            BeginInvoke(populate);
        else
            populate();
    }

    // -------------------------------------------------------------------------
    // Grid event handlers
    // -------------------------------------------------------------------------

    private void Dgv_SelectionChanged(object? sender, EventArgs e) => UpdateButtonStates();

    private void Dgv_CellFormatting(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.Value is not string text) return;

        // Column 3 = Priority
        if (e.ColumnIndex == 3)
        {
            e.CellStyle.ForeColor = GetPriorityColor(text);
            e.CellStyle.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
            e.FormattingApplied = true;
        }
    }

    private void Dgv_CellDoubleClick(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0 || e.RowIndex >= _rows.Count) return;
        OpenEditDialog(_rows[e.RowIndex]);
    }

    // -------------------------------------------------------------------------
    // Button handlers
    // -------------------------------------------------------------------------

    private void BtnAddRequest_Click(object? sender, EventArgs e)
    {
        using var dlg = new RequestDialog("Add Request", null);
        if (dlg.ShowDialog(this) != DialogResult.OK) return;

        Task.Run(async () =>
        {
            try
            {
                await _ipc.SendCommandAsync<object>("create_request", dlg.BuildPayload());
                await LoadDataAsync();
            }
            catch (Exception ex)
            {
                BeginInvoke(() =>
                    MessageBox.Show(this, $"Failed to create request:\n{ex.Message}",
                        "Error", MessageBoxButtons.OK, MessageBoxIcon.Error));
            }
        });
    }

    private void BtnEdit_Click(object? sender, EventArgs e)
    {
        var request = GetSelectedRequest();
        if (request is null) return;
        OpenEditDialog(request);
    }

    private void BtnViewDetails_Click(object? sender, EventArgs e)
    {
        var request = GetSelectedRequest();
        if (request is null) return;
        OpenEditDialog(request, readOnly: true);
    }

    private void BtnCreateEstimation_Click(object? sender, EventArgs e)
    {
        var request = GetSelectedRequest();
        if (request is null) return;
        _mainForm.NavigateTo("NewEstimation", request.Id);
    }

    // -------------------------------------------------------------------------
    // Edit dialog helpers
    // -------------------------------------------------------------------------

    private void OpenEditDialog(Request request, bool readOnly = false)
    {
        using var dlg = new RequestDialog(readOnly ? "Request Details" : "Edit Request", request);
        dlg.SetReadOnly(readOnly);

        if (dlg.ShowDialog(this) != DialogResult.OK || readOnly) return;

        var payload = dlg.BuildPayload();

        Task.Run(async () =>
        {
            try
            {
                await _ipc.SendCommandAsync<object>("update_request", payload);
                await LoadDataAsync();
            }
            catch (Exception ex)
            {
                BeginInvoke(() =>
                    MessageBox.Show(this, $"Failed to update request:\n{ex.Message}",
                        "Error", MessageBoxButtons.OK, MessageBoxIcon.Error));
            }
        });
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private Request? GetSelectedRequest()
    {
        if (_dgv.SelectedRows.Count == 0) return null;
        int idx = _dgv.SelectedRows[0].Index;
        if (idx < 0 || idx >= _rows.Count) return null;
        return _rows[idx];
    }

    private void UpdateButtonStates()
    {
        Action update = () =>
        {
            bool hasSelection = _dgv.SelectedRows.Count > 0;
            _btnCreateEstimation.Enabled = hasSelection;
            _btnEdit.Enabled = hasSelection;
            _btnViewDetails.Enabled = hasSelection;
        };

        if (InvokeRequired)
            BeginInvoke(update);
        else
            update();
    }

    private void SetStatus(string text, Color color)
    {
        Action set = () =>
        {
            if (IsDisposed) return;
            _lblStatus.Text = text;
            _lblStatus.ForeColor = color;
        };

        if (InvokeRequired)
            BeginInvoke(set);
        else
            set();
    }

    private static string FormatDate(string? iso)
    {
        if (string.IsNullOrWhiteSpace(iso)) return "";
        if (DateTime.TryParse(iso, out var dt))
            return dt.ToString("yyyy-MM-dd");
        return iso;
    }

    private static Color GetPriorityColor(string priority) =>
        priority?.ToUpperInvariant() switch
        {
            "CRITICAL" => ThemeHelper.FeasibilityRed,
            "HIGH"     => ThemeHelper.FeasibilityAmber,
            "MEDIUM"   => ThemeHelper.Text,
            "LOW"      => ThemeHelper.TextSecondary,
            _          => ThemeHelper.TextSecondary,
        };
}

// =============================================================================
// RequestDialog — inline dialog for Add / Edit / View
// =============================================================================

/// <summary>
/// Modal dialog for creating or editing a Request. Accepts an optional
/// existing <see cref="Request"/> to pre-populate fields. When <paramref name="existing"/>
/// is null the dialog is in create mode; when non-null it is in edit mode.
/// Call <see cref="SetReadOnly"/> before <c>ShowDialog</c> for view-only mode.
/// Call <see cref="BuildPayload"/> after <c>DialogResult.OK</c> to get the
/// object suitable for sending to the IPC backend.
/// </summary>
internal sealed class RequestDialog : Form
{
    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly Request? _existing;

    private TextBox _txtTitle = null!;
    private TextBox _txtDescription = null!;
    private TextBox _txtRequesterName = null!;
    private TextBox _txtRequesterEmail = null!;
    private TextBox _txtBusinessUnit = null!;
    private ComboBox _cmbPriority = null!;
    private DateTimePicker _dtpDelivery = null!;
    private CheckBox _chkHasDelivery = null!;
    private TextBox _txtNotes = null!;
    private Button _btnSave = null!;
    private Button _btnCancel = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public RequestDialog(string title, Request? existing)
    {
        _existing = existing;

        Text = title;
        Size = new Size(520, 560);
        MinimumSize = new Size(480, 520);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        BackColor = ThemeHelper.Background;
        ForeColor = ThemeHelper.Text;

        BuildLayout();
        PopulateFields();
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /// <summary>Disables all editable controls, turning the dialog read-only.</summary>
    public void SetReadOnly(bool readOnly)
    {
        if (!readOnly) return;

        foreach (Control c in Controls)
            SetControlReadOnly(c, readOnly);

        _btnSave.Visible = false;
        _btnCancel.Text = "Close";
    }

    /// <summary>
    /// Builds a payload object matching the IPC <c>create_request</c> /
    /// <c>update_request</c> command schemas. Includes <c>id</c> when editing.
    /// </summary>
    public object BuildPayload()
    {
        var deliveryDate = _chkHasDelivery.Checked
            ? _dtpDelivery.Value.ToString("yyyy-MM-dd")
            : (string?)null;

        if (_existing is not null)
        {
            return new
            {
                id = _existing.Id,
                title = _txtTitle.Text.Trim(),
                description = string.IsNullOrWhiteSpace(_txtDescription.Text) ? null : _txtDescription.Text.Trim(),
                requester_name = _txtRequesterName.Text.Trim(),
                requester_email = string.IsNullOrWhiteSpace(_txtRequesterEmail.Text) ? null : _txtRequesterEmail.Text.Trim(),
                business_unit = string.IsNullOrWhiteSpace(_txtBusinessUnit.Text) ? null : _txtBusinessUnit.Text.Trim(),
                priority = _cmbPriority.SelectedItem?.ToString() ?? "MEDIUM",
                requested_delivery_date = deliveryDate,
                notes = string.IsNullOrWhiteSpace(_txtNotes.Text) ? null : _txtNotes.Text.Trim(),
            };
        }

        return new
        {
            title = _txtTitle.Text.Trim(),
            description = string.IsNullOrWhiteSpace(_txtDescription.Text) ? null : _txtDescription.Text.Trim(),
            requester_name = _txtRequesterName.Text.Trim(),
            requester_email = string.IsNullOrWhiteSpace(_txtRequesterEmail.Text) ? null : _txtRequesterEmail.Text.Trim(),
            business_unit = string.IsNullOrWhiteSpace(_txtBusinessUnit.Text) ? null : _txtBusinessUnit.Text.Trim(),
            priority = _cmbPriority.SelectedItem?.ToString() ?? "MEDIUM",
            requested_delivery_date = deliveryDate,
            notes = string.IsNullOrWhiteSpace(_txtNotes.Text) ? null : _txtNotes.Text.Trim(),
        };
    }

    // -------------------------------------------------------------------------
    // Layout
    // -------------------------------------------------------------------------

    private void BuildLayout()
    {
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            Padding = new Padding(16, 12, 16, 8),
            BackColor = ThemeHelper.Background,
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 140));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));

        int row = 0;

        // Title (required)
        AddFormRow(layout, row++, "Title *", _txtTitle = CreateTextBox());

        // Description (multiline)
        _txtDescription = CreateTextBox(multiline: true, height: 70);
        AddFormRow(layout, row++, "Description", _txtDescription);

        // Requester Name
        AddFormRow(layout, row++, "Requester Name *", _txtRequesterName = CreateTextBox());

        // Requester Email
        AddFormRow(layout, row++, "Requester Email", _txtRequesterEmail = CreateTextBox());

        // Business Unit
        AddFormRow(layout, row++, "Business Unit", _txtBusinessUnit = CreateTextBox());

        // Priority
        _cmbPriority = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
        _cmbPriority.Items.AddRange(new object[] { "LOW", "MEDIUM", "HIGH", "CRITICAL" });
        _cmbPriority.SelectedIndex = 1;
        ThemeHelper.StyleComboBox(_cmbPriority);
        AddFormRow(layout, row++, "Priority", _cmbPriority);

        // Delivery date — optional, gated by checkbox
        var deliveryPanel = BuildDeliveryPanel();
        AddFormRow(layout, row++, "Delivery Date", deliveryPanel);

        // Notes
        _txtNotes = CreateTextBox(multiline: true, height: 60);
        AddFormRow(layout, row++, "Notes", _txtNotes);

        // Add a spacer row that takes the remaining space
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
        layout.RowCount = row + 1;

        // Button row
        var btnPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 48,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(16, 8, 16, 8),
        };

        _btnCancel = new Button { Text = "Cancel", Width = 90, Height = 30 };
        ThemeHelper.StyleButton(_btnCancel, isPrimary: false);
        _btnCancel.Click += (_, _) => { DialogResult = DialogResult.Cancel; Close(); };
        _btnCancel.Dock = DockStyle.Right;
        btnPanel.Controls.Add(_btnCancel);

        _btnSave = new Button { Text = "Save", Width = 90, Height = 30 };
        ThemeHelper.StyleButton(_btnSave, isPrimary: true);
        _btnSave.Click += BtnSave_Click;
        _btnSave.Dock = DockStyle.Right;
        btnPanel.Controls.Add(_btnSave);

        var separator = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 1,
            BackColor = ThemeHelper.Border,
        };

        Controls.Add(layout);
        Controls.Add(separator);
        Controls.Add(btnPanel);
    }

    private Panel BuildDeliveryPanel()
    {
        var panel = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent, Height = 28 };

        _chkHasDelivery = new CheckBox
        {
            Text = "Set date",
            AutoSize = true,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 9f),
            Location = new Point(0, 5),
        };

        _dtpDelivery = new DateTimePicker
        {
            Format = DateTimePickerFormat.Short,
            CalendarForeColor = ThemeHelper.Text,
            CalendarMonthBackground = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Location = new Point(75, 2),
            Width = 130,
            Enabled = false,
        };

        _chkHasDelivery.CheckedChanged += (_, _) => _dtpDelivery.Enabled = _chkHasDelivery.Checked;

        panel.Controls.Add(_chkHasDelivery);
        panel.Controls.Add(_dtpDelivery);
        return panel;
    }

    private static void AddFormRow(TableLayoutPanel layout, int row, string labelText, Control field)
    {
        // Ensure enough rows are defined
        while (layout.RowStyles.Count <= row)
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        layout.RowCount = Math.Max(layout.RowCount, row + 1);

        var lbl = new Label
        {
            Text = labelText,
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.MiddleLeft,
            Margin = new Padding(0, 0, 8, 4),
        };

        field.Margin = new Padding(0, 0, 0, 8);

        layout.Controls.Add(lbl, 0, row);
        layout.Controls.Add(field, 1, row);
    }

    // -------------------------------------------------------------------------
    // Pre-population
    // -------------------------------------------------------------------------

    private void PopulateFields()
    {
        if (_existing is null) return;

        _txtTitle.Text = _existing.Title;
        _txtDescription.Text = _existing.Description ?? "";
        _txtRequesterName.Text = _existing.RequesterName;
        _txtRequesterEmail.Text = _existing.RequesterEmail ?? "";
        _txtBusinessUnit.Text = _existing.BusinessUnit ?? "";
        _txtNotes.Text = _existing.Notes ?? "";

        // Priority
        int priorityIndex = _cmbPriority.Items.IndexOf(_existing.Priority);
        _cmbPriority.SelectedIndex = priorityIndex >= 0 ? priorityIndex : 1;

        // Delivery date
        if (!string.IsNullOrWhiteSpace(_existing.RequestedDeliveryDate) &&
            DateTime.TryParse(_existing.RequestedDeliveryDate, out var dt))
        {
            _chkHasDelivery.Checked = true;
            _dtpDelivery.Value = dt;
            _dtpDelivery.Enabled = true;
        }
    }

    // -------------------------------------------------------------------------
    // Validation & save
    // -------------------------------------------------------------------------

    private void BtnSave_Click(object? sender, EventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_txtTitle.Text))
        {
            MessageBox.Show(this, "Title is required.", "Validation",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            _txtTitle.Focus();
            return;
        }

        if (string.IsNullOrWhiteSpace(_txtRequesterName.Text))
        {
            MessageBox.Show(this, "Requester Name is required.", "Validation",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            _txtRequesterName.Focus();
            return;
        }

        DialogResult = DialogResult.OK;
        Close();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static TextBox CreateTextBox(bool multiline = false, int height = 24)
    {
        var txt = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = multiline,
        };
        if (multiline) txt.Height = height;
        ThemeHelper.StyleTextBox(txt);
        return txt;
    }

    private static void SetControlReadOnly(Control control, bool readOnly)
    {
        switch (control)
        {
            case TextBox txt:
                txt.ReadOnly = readOnly;
                txt.BackColor = ThemeHelper.Surface;
                break;
            case ComboBox cmb:
                cmb.Enabled = !readOnly;
                break;
            case DateTimePicker dtp:
                dtp.Enabled = !readOnly;
                break;
            case CheckBox chk:
                chk.Enabled = !readOnly;
                break;
        }

        foreach (Control child in control.Controls)
            SetControlReadOnly(child, readOnly);
    }
}
