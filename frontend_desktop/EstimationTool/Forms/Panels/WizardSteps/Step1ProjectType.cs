using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step1ProjectType : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class RequestsResponse
    {
        [JsonPropertyName("requests")] public List<Request> Requests { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly WizardPanel.WizardState _state;

    private ComboBox _cmbRequest = null!;
    private TextBox  _txtProjectName = null!;
    private TextBox  _txtCreatedBy = null!;

    private RadioButton _rbNew       = null!;
    private RadioButton _rbEvolution = null!;
    private RadioButton _rbSupport   = null!;

    private Label _lblRequestInfo = null!;

    private List<Request> _requests = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step1ProjectType(BackendApiService ipc, WizardPanel.WizardState state)
    {
        _ipc   = ipc;
        _state = state;

        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;
        AutoScroll = true;

        BuildUI();
        PopulateFromState();

        Load += async (_, _) => await LoadRequestsAsync();
    }

    // -------------------------------------------------------------------------
    // UI construction
    // -------------------------------------------------------------------------

    private void BuildUI()
    {
        var scroll = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = ThemeHelper.Background,
        };
        Controls.Add(scroll);

        int y = 0;

        // Header
        var lblHeader = new Label
        {
            Text = "Step 1: Project Information",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            AutoSize = true,
            Location = new Point(0, y),
        };
        scroll.Controls.Add(lblHeader);
        y += 40;

        var divider = new Panel
        {
            BackColor = ThemeHelper.Border,
            Height = 1,
            Left = 0, Top = y, Width = 600,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        scroll.Controls.Add(divider);
        y += 16;

        // ---- Request linkage -----------------------------------------------
        var lblReqSection = MakeSectionLabel("Linked Request (Optional)", y);
        scroll.Controls.Add(lblReqSection);
        y += 24;

        if (_state.RequestId.HasValue)
        {
            // Show static info — we will populate once requests load
            _lblRequestInfo = new Label
            {
                Text = $"Linked to request ID #{_state.RequestId}",
                ForeColor = ThemeHelper.FeasibilityGreen,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 9f),
                AutoSize = true,
                Location = new Point(0, y),
            };
            scroll.Controls.Add(_lblRequestInfo);
            y += 28;

            // Hidden combo still created for layout consistency (invisible)
            _cmbRequest = new ComboBox { Visible = false };
        }
        else
        {
            var lblReq = MakeFieldLabel("Select Request", y);
            scroll.Controls.Add(lblReq);
            y += 20;

            _cmbRequest = new ComboBox
            {
                Location = new Point(0, y),
                Width = 420,
                DropDownStyle = ComboBoxStyle.DropDownList,
            };
            ThemeHelper.StyleComboBox(_cmbRequest);
            scroll.Controls.Add(_cmbRequest);

            _lblRequestInfo = new Label
            {
                ForeColor = ThemeHelper.TextSecondary,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 8.5f),
                AutoSize = true,
                Location = new Point(0, y + 30),
            };
            scroll.Controls.Add(_lblRequestInfo);

            _cmbRequest.SelectedIndexChanged += CmbRequest_SelectedIndexChanged;
            y += 56;
        }

        y += 8;

        // ---- Project name --------------------------------------------------
        var lblNameSection = MakeSectionLabel("Project Details", y);
        scroll.Controls.Add(lblNameSection);
        y += 24;

        var lblName = MakeFieldLabel("Project Name *", y);
        scroll.Controls.Add(lblName);
        y += 20;

        _txtProjectName = new TextBox
        {
            Location = new Point(0, y),
            Width = 420,
        };
        ThemeHelper.StyleTextBox(_txtProjectName);
        scroll.Controls.Add(_txtProjectName);
        y += 36;

        // ---- Created by ----------------------------------------------------
        var lblCreatedBy = MakeFieldLabel("Created By", y);
        scroll.Controls.Add(lblCreatedBy);
        y += 20;

        _txtCreatedBy = new TextBox
        {
            Location = new Point(0, y),
            Width = 280,
        };
        ThemeHelper.StyleTextBox(_txtCreatedBy);
        scroll.Controls.Add(_txtCreatedBy);
        y += 44;

        // ---- Project type --------------------------------------------------
        var lblTypeSection = MakeSectionLabel("Project Type *", y);
        scroll.Controls.Add(lblTypeSection);
        y += 24;

        var typeOptions = new[]
        {
            ("NEW",       "New Project",   "Brand new feature set — all tasks start from scratch."),
            ("EVOLUTION", "Evolution",     "Enhancing an existing product — some existing tests apply."),
            ("SUPPORT",   "Support",       "Maintenance, bug fixes, and regression testing on a known product."),
        };

        foreach (var (value, label, description) in typeOptions)
        {
            var card = new Panel
            {
                Location = new Point(0, y),
                Width = 540,
                Height = 64,
                BackColor = ThemeHelper.Surface,
                Cursor = Cursors.Hand,
            };
            ThemeHelper.StylePanel(card);
            scroll.Controls.Add(card);

            var rb = new RadioButton
            {
                Text = label,
                Tag  = value,
                Font = new Font("Segoe UI", 10f, FontStyle.Regular),
                ForeColor = ThemeHelper.Text,
                BackColor = Color.Transparent,
                Location = new Point(12, 10),
                AutoSize = true,
            };

            var descLabel = new Label
            {
                Text = description,
                ForeColor = ThemeHelper.TextSecondary,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 8.5f),
                Location = new Point(32, 32),
                AutoSize = true,
            };

            card.Controls.Add(rb);
            card.Controls.Add(descLabel);

            // Clicking the card selects the radio button
            card.Click += (_, _) => rb.Checked = true;
            descLabel.Click += (_, _) => rb.Checked = true;

            switch (value)
            {
                case "NEW":       _rbNew       = rb; break;
                case "EVOLUTION": _rbEvolution = rb; break;
                case "SUPPORT":   _rbSupport   = rb; break;
            }

            y += 74;
        }

        scroll.AutoScrollMinSize = new Size(0, y + 16);
    }

    // -------------------------------------------------------------------------
    // Async data loading
    // -------------------------------------------------------------------------

    private async Task LoadRequestsAsync()
    {
        if (_state.RequestId.HasValue)
        {
            // Still load to display linked request info
            try
            {
                var resp = await _ipc.SendCommandAsync<RequestsResponse>("get_requests");
                _requests = resp.Requests;
                var linked = _requests.FirstOrDefault(r => r.Id == _state.RequestId.Value);
                if (linked != null && _lblRequestInfo != null)
                {
                    if (InvokeRequired)
                        BeginInvoke(() => _lblRequestInfo.Text =
                            $"Linked to: [{linked.RequestNumber}] {linked.Title}  — {linked.RequesterName}");
                    else
                        _lblRequestInfo.Text =
                            $"Linked to: [{linked.RequestNumber}] {linked.Title}  — {linked.RequesterName}";
                }
            }
            catch { /* non-critical */ }
            return;
        }

        try
        {
            var resp = await _ipc.SendCommandAsync<RequestsResponse>("get_requests");
            _requests = resp.Requests;

            if (InvokeRequired)
                BeginInvoke(PopulateCombo);
            else
                PopulateCombo();
        }
        catch (Exception ex)
        {
            if (InvokeRequired)
                BeginInvoke(() => _lblRequestInfo.Text = $"Could not load requests: {ex.Message}");
            else
                _lblRequestInfo.Text = $"Could not load requests: {ex.Message}";
        }
    }

    private void PopulateCombo()
    {
        _cmbRequest.Items.Clear();
        _cmbRequest.Items.Add("-- None --");

        foreach (var r in _requests)
            _cmbRequest.Items.Add(new RequestComboItem(r));

        // Re-select if state already has a request id (shouldn't happen here but be safe)
        if (_state.RequestId.HasValue)
        {
            for (int i = 1; i < _cmbRequest.Items.Count; i++)
            {
                if (_cmbRequest.Items[i] is RequestComboItem item && item.Request.Id == _state.RequestId.Value)
                {
                    _cmbRequest.SelectedIndex = i;
                    return;
                }
            }
        }

        _cmbRequest.SelectedIndex = 0;
    }

    private void CmbRequest_SelectedIndexChanged(object? sender, EventArgs e)
    {
        if (_cmbRequest.SelectedItem is RequestComboItem item)
        {
            _lblRequestInfo.Text =
                $"{item.Request.Priority} priority  |  Requester: {item.Request.RequesterName}" +
                (item.Request.RequestedDeliveryDate != null
                    ? $"  |  Requested delivery: {item.Request.RequestedDeliveryDate}"
                    : "");

            // Pre-fill project name if empty
            if (string.IsNullOrWhiteSpace(_txtProjectName.Text))
                _txtProjectName.Text = item.Request.Title;
        }
        else
        {
            _lblRequestInfo.Text = "";
        }
    }

    // -------------------------------------------------------------------------
    // State population
    // -------------------------------------------------------------------------

    private void PopulateFromState()
    {
        _txtProjectName.Text = _state.ProjectName;
        _txtCreatedBy.Text   = _state.CreatedBy;

        switch (_state.ProjectType)
        {
            case "EVOLUTION": _rbEvolution.Checked = true; break;
            case "SUPPORT":   _rbSupport.Checked   = true; break;
            default:          _rbNew.Checked        = true; break;
        }
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public bool Validate(out string error)
    {
        if (string.IsNullOrWhiteSpace(_txtProjectName.Text))
        {
            error = "Project Name is required.";
            return false;
        }

        if (!_rbNew.Checked && !_rbEvolution.Checked && !_rbSupport.Checked)
        {
            error = "Please select a Project Type.";
            return false;
        }

        error = "";
        return true;
    }

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.ProjectName = _txtProjectName.Text.Trim();
        state.CreatedBy   = _txtCreatedBy.Text.Trim();

        state.ProjectType = _rbEvolution.Checked ? "EVOLUTION"
                          : _rbSupport.Checked   ? "SUPPORT"
                          : "NEW";

        if (!_state.RequestId.HasValue && _cmbRequest.SelectedItem is RequestComboItem item)
            state.RequestId = item.Request.Id;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Label MakeSectionLabel(string text, int y) => new()
    {
        Text = text,
        Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
        ForeColor = ThemeHelper.Text,
        BackColor = Color.Transparent,
        AutoSize = true,
        Location = new Point(0, y),
    };

    private static Label MakeFieldLabel(string text, int y) => new()
    {
        Text = text,
        Font = new Font("Segoe UI", 8.5f),
        ForeColor = ThemeHelper.TextSecondary,
        BackColor = Color.Transparent,
        AutoSize = true,
        Location = new Point(0, y),
    };

    // -------------------------------------------------------------------------
    // Combo item wrapper
    // -------------------------------------------------------------------------

    private sealed class RequestComboItem(Request request)
    {
        public Request Request { get; } = request;
        public override string ToString() => $"[{Request.RequestNumber}] {Request.Title}";
    }
}
