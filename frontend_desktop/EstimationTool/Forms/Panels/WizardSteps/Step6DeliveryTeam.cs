using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step6DeliveryTeam : UserControl
{
    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    private const double WorkingHoursPerDay = 7.0;

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly WizardPanel.WizardState _state;

    // Suppress event loops during auto-fill
    private bool _suppressRecalc;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step6DeliveryTeam(WizardPanel.WizardState state)
    {
        _state = state;

        InitializeComponent();

        // Wire events
        _dtpDelivery.ValueChanged     += DtpDelivery_ValueChanged;
        _chkNoDeadline.CheckedChanged += ChkNoDeadline_CheckedChanged;
        _nudWorkingDays.ValueChanged  += (_, _) => UpdateCapacity();
        _nudTeamSize.ValueChanged     += (_, _) => UpdateCapacity();
        _chkHasLeader.CheckedChanged  += (_, _) => UpdateCapacity();

        PopulateFromState();
    }

    // -------------------------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------------------------

    private void DtpDelivery_ValueChanged(object? sender, EventArgs e)
    {
        if (_suppressRecalc || _chkNoDeadline.Checked) return;

        // Count business days from today to the selected date
        var days = CountWorkingDays(DateTime.Today, _dtpDelivery.Value.Date);
        _suppressRecalc = true;
        _nudWorkingDays.Value = Math.Max(1, Math.Min(_nudWorkingDays.Maximum, days));
        _suppressRecalc = false;

        UpdateCapacity();
    }

    private void ChkNoDeadline_CheckedChanged(object? sender, EventArgs e)
    {
        _dtpDelivery.Enabled = !_chkNoDeadline.Checked;
        UpdateCapacity();
    }

    private void UpdateCapacity()
    {
        if (_suppressRecalc) return;

        int    days     = (int)_nudWorkingDays.Value;
        int    teamSize = (int)_nudTeamSize.Value;
        double capacity = days * teamSize * WorkingHoursPerDay;

        _lblCapacity.Text =
            $"Team capacity = {days} days  x  {teamSize} tester(s)  x  {WorkingHoursPerDay}h/day  =  {capacity:F0} h";

        // Animate bar to represent relative utilisation (bar is always full here — just a visual)
        double maxCapacity = 365 * 50 * WorkingHoursPerDay;
        double fillPct     = Math.Min(1.0, capacity / maxCapacity);
        int barWidth       = (int)(_pnlCapacityBar.Width * fillPct);
        _pnlCapacityFill.Width = Math.Max(0, barWidth);
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    private void PopulateFromState()
    {
        _suppressRecalc = true;

        if (_state.DeliveryDate.HasValue)
        {
            _dtpDelivery.Value     = _state.DeliveryDate.Value;
            _chkNoDeadline.Checked = false;
        }
        else
        {
            _chkNoDeadline.Checked = true;
            _dtpDelivery.Enabled   = false;
        }

        _nudWorkingDays.Value = Math.Max(1, Math.Min(_nudWorkingDays.Maximum, _state.WorkingDays));
        _nudTeamSize.Value    = Math.Max(1, Math.Min(_nudTeamSize.Maximum, _state.TeamSize));
        _chkHasLeader.Checked = _state.HasLeader;

        _suppressRecalc = false;
        UpdateCapacity();
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public bool Validate(out string error)
    {
        if ((int)_nudWorkingDays.Value < 1)
        {
            error = "Working Days must be at least 1.";
            return false;
        }
        if ((int)_nudTeamSize.Value < 1)
        {
            error = "Team Size must be at least 1.";
            return false;
        }
        error = "";
        return true;
    }

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.DeliveryDate = _chkNoDeadline.Checked ? null : _dtpDelivery.Value.Date;
        state.WorkingDays  = (int)_nudWorkingDays.Value;
        state.TeamSize     = (int)_nudTeamSize.Value;
        state.HasLeader    = _chkHasLeader.Checked;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static int CountWorkingDays(DateTime start, DateTime end)
    {
        if (end <= start) return 1;
        int days    = 0;
        var current = start.AddDays(1);
        while (current <= end)
        {
            if (current.DayOfWeek != DayOfWeek.Saturday && current.DayOfWeek != DayOfWeek.Sunday)
                days++;
            current = current.AddDays(1);
        }
        return Math.Max(1, days);
    }
}
