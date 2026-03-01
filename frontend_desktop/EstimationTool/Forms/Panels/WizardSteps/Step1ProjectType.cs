using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step1ProjectType : UserControl
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

    private ComboBox _cmbRequest    = null!;
    private TextBox  _txtProjectName = null!;
    private TextBox  _txtCreatedBy   = null!;

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

        InitializeComponent();
        WireRemainingControls();
        PopulateFromState();

        Load += async (_, _) => await LoadRequestsAsync();
    }

    // -------------------------------------------------------------------------
    // Post-InitializeComponent wiring
    // Allocates the conditional/input controls, inserts them into _pnlScroll,
    // and repositions the downstream labels/fields to maintain the original
    // y-layout from BuildUI().
    // -------------------------------------------------------------------------

    private void WireRemainingControls()
    {
        // The Designer reserved placeholder y-offsets matching the original
        // BuildUI() layout. We need to:
        //   1. Create the input/conditional controls
        //   2. Insert them into _pnlScroll at the correct positions
        //   3. Wire card-click events on the type cards
        //   4. Set AutoScrollMinSize

        // The Designer lays out static labels up to y = 108 (after _lblReqSection).
        // From there, the conditional block occupies either:
        //   - RequestId set:   static _lblRequestInfo at y=108, combo hidden  (height = 28)
        //   - No RequestId:    _lblReqField at y=108 (+20), combo at y=128 (+56), _lblRequestInfo at y=158 (+8 gap)
        //
        // After the conditional block the Designer's _lblDetailsSection is positioned
        // in InitializeComponent at a reserved placeholder. Because we can't set
        // coordinates in InitializeComponent based on runtime state, we relocate
        // the downstream controls here.

        const int baseAfterHeader   = 56;  // y after divider
        const int reqSectionHeight  = 24;  // _lblReqSection
        const int reqSectionY       = baseAfterHeader; // 56

        // ---- Build _cmbRequest and _lblRequestInfo --------------------------

        if (_state.RequestId.HasValue)
        {
            // Static info label — shown, combo hidden
            _lblRequestInfo = new Label
            {
                Text      = $"Linked to request ID #{_state.RequestId}",
                ForeColor = ThemeHelper.FeasibilityGreen,
                BackColor = Color.Transparent,
                Font      = new Font("Segoe UI", 9f),
                AutoSize  = true,
                Location  = new Point(0, reqSectionY + reqSectionHeight),
            };
            _pnlScroll.Controls.Add(_lblRequestInfo);

            // Hidden combo for layout consistency
            _cmbRequest = new ComboBox { Visible = false };
            _pnlScroll.Controls.Add(_cmbRequest);

            // Hide the "Select Request" field label created by the Designer
            _lblReqField.Visible = false;

            // Reposition downstream sections to follow static label (28 px) + 8 gap
            RelocateSectionsAfterRequest(reqSectionY + reqSectionHeight + 28 + 8);
        }
        else
        {
            // Show "Select Request" field label
            _lblReqField.Location = new Point(0, reqSectionY + reqSectionHeight);
            _lblReqField.Visible  = true;

            int comboY = reqSectionY + reqSectionHeight + 20;

            _cmbRequest = new ComboBox
            {
                Location     = new Point(0, comboY),
                Width        = 420,
                DropDownStyle = ComboBoxStyle.DropDownList,
            };
            ThemeHelper.StyleComboBox(_cmbRequest);

            _lblRequestInfo = new Label
            {
                ForeColor = ThemeHelper.TextSecondary,
                BackColor = Color.Transparent,
                Font      = new Font("Segoe UI", 8.5f),
                AutoSize  = true,
                Location  = new Point(0, comboY + 30),
            };

            _pnlScroll.Controls.Add(_cmbRequest);
            _pnlScroll.Controls.Add(_lblRequestInfo);

            _cmbRequest.SelectedIndexChanged += CmbRequest_SelectedIndexChanged;

            // Reposition downstream sections: comboY + 56 (combo row) + 8 gap
            RelocateSectionsAfterRequest(comboY + 56 + 8);
        }

        // ---- Build _txtProjectName and _txtCreatedBy ------------------------
        // These are positioned relative to _lblDetailsSection and _lblNameField,
        // whose Locations are set by RelocateSectionsAfterRequest().
        // We position them just below their respective field labels (+20 each).

        _txtProjectName = new TextBox
        {
            Location = new Point(0, _lblNameField.Top + 20),
            Width    = 420,
        };
        ThemeHelper.StyleTextBox(_txtProjectName);
        _pnlScroll.Controls.Add(_txtProjectName);

        _txtCreatedBy = new TextBox
        {
            Location = new Point(0, _lblCreatedByField.Top + 20),
            Width    = 280,
        };
        ThemeHelper.StyleTextBox(_txtCreatedBy);
        _pnlScroll.Controls.Add(_txtCreatedBy);

        // ---- Wire card-click events on the type cards -----------------------
        _cardNew.Click       += (_, _) => _rbNew.Checked       = true;
        _lblNewDesc.Click    += (_, _) => _rbNew.Checked       = true;

        _cardEvolution.Click     += (_, _) => _rbEvolution.Checked = true;
        _lblEvolutionDesc.Click  += (_, _) => _rbEvolution.Checked = true;

        _cardSupport.Click   += (_, _) => _rbSupport.Checked   = true;
        _lblSupportDesc.Click += (_, _) => _rbSupport.Checked  = true;

        // ---- AutoScrollMinSize ----------------------------------------------
        // Last card bottom = _cardSupport.Bottom + 16
        _pnlScroll.AutoScrollMinSize = new Size(0, _cardSupport.Bottom + 16);
    }

    /// <summary>
    /// Repositions all controls that follow the request-linkage block so
    /// the layout is consistent regardless of which branch was taken.
    /// </summary>
    private void RelocateSectionsAfterRequest(int startY)
    {
        // ---- Project Details section ----------------------------------------
        int y = startY;

        _lblDetailsSection.Location = new Point(0, y);
        y += 24;

        _lblNameField.Location = new Point(0, y);
        y += 20;
        // _txtProjectName placed at y (set in WireRemainingControls after this returns)
        y += 36;

        _lblCreatedByField.Location = new Point(0, y);
        y += 20;
        // _txtCreatedBy placed at y
        y += 44;

        // ---- Project Type section -------------------------------------------
        _lblTypeSection.Location = new Point(0, y);
        y += 24;

        _cardNew.Location       = new Point(0, y); y += 74;
        _cardEvolution.Location = new Point(0, y); y += 74;
        _cardSupport.Location   = new Point(0, y);
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
    // Combo item wrapper
    // -------------------------------------------------------------------------

    private sealed class RequestComboItem(Request request)
    {
        public Request Request { get; } = request;
        public override string ToString() => $"[{Request.RequestNumber}] {Request.Title}";
    }
}
