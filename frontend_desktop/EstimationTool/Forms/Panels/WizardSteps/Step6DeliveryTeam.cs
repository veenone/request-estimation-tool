using EstimationTool.Services;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step6DeliveryTeam : UserControl
{
    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    private const double WorkingHoursPerDay = 7.0;

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly WizardPanel.WizardState _state;

    private DateTimePicker  _dtpDelivery    = null!;
    private CheckBox        _chkNoDeadline  = null!;
    private NumericUpDown   _nudWorkingDays = null!;
    private NumericUpDown   _nudTeamSize    = null!;
    private CheckBox        _chkHasLeader   = null!;
    private Label           _lblCapacity    = null!;
    private Panel           _pnlCapacityBar = null!;
    private Panel           _pnlCapacityFill = null!;

    // Suppress event loops during auto-fill
    private bool _suppressRecalc;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step6DeliveryTeam(WizardPanel.WizardState state)
    {
        _state = state;

        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        BuildUI();
        PopulateFromState();
    }

    // -------------------------------------------------------------------------
    // UI construction
    // -------------------------------------------------------------------------

    private void BuildUI()
    {
        var layout = new TableLayoutPanel
        {
            Dock      = DockStyle.Fill,
            RowCount  = 3,
            ColumnCount = 1,
            BackColor = ThemeHelper.Background,
        };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 380));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        // Header
        var lblHeader = new Label
        {
            Text = "Step 6: Delivery & Team",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        layout.Controls.Add(lblHeader, 0, 0);

        // Form card
        var card = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Width = 520,
            Height = 370,
            Anchor = AnchorStyles.Top | AnchorStyles.Left,
        };
        ThemeHelper.StylePanel(card);
        layout.Controls.Add(card, 0, 1);

        int y = 16;

        // ---- Delivery date section -----------------------------------------
        AddSectionLabel(card, "Delivery Timeline", ref y);

        AddFieldLabel(card, "Expected Delivery Date", y);
        y += 22;

        _dtpDelivery = new DateTimePicker
        {
            Location = new Point(16, y),
            Width    = 200,
            Format   = DateTimePickerFormat.Short,
            MinDate  = DateTime.Today,
            CalendarForeColor = ThemeHelper.Text,
            CalendarMonthBackground = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 9f),
        };
        card.Controls.Add(_dtpDelivery);

        _chkNoDeadline = new CheckBox
        {
            Text      = "No fixed deadline",
            Location  = new Point(220, y + 4),
            AutoSize  = true,
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 9f),
        };
        card.Controls.Add(_chkNoDeadline);
        y += 38;

        AddFieldLabel(card, "Working Days Available *", y);
        y += 22;

        _nudWorkingDays = MakeNud(card, y, 1, 365, 20, width: 100);
        y += 38;

        var lblDaysHint = new Label
        {
            Text = "Tip: set the delivery date above to auto-calculate working days.",
            Location = new Point(16, y),
            AutoSize = true,
            Font = new Font("Segoe UI", 8f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
        };
        card.Controls.Add(lblDaysHint);
        y += 28;

        // ---- Team section -------------------------------------------------
        AddSectionLabel(card, "Team Composition", ref y);

        AddFieldLabel(card, "Number of Testers *", y);
        y += 22;
        _nudTeamSize = MakeNud(card, y, 1, 50, 1, width: 100);
        y += 38;

        _chkHasLeader = new CheckBox
        {
            Text      = "Include Test Leader  (leader effort = 50% of total tester effort)",
            Location  = new Point(16, y),
            AutoSize  = true,
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 9f),
        };
        card.Controls.Add(_chkHasLeader);
        y += 32;

        // ---- Capacity info bar -------------------------------------------
        y += 8;
        var capPanel = new Panel
        {
            Location  = new Point(16, y),
            Width     = 480,
            Height    = 60,
            BackColor = ThemeHelper.Sidebar,
        };

        _lblCapacity = new Label
        {
            Dock      = DockStyle.Top,
            Height    = 28,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        // Simple capacity bar (purely visual)
        var barBg = new Panel
        {
            Dock      = DockStyle.Top,
            Height    = 6,
            BackColor = ThemeHelper.Border,
        };
        _pnlCapacityFill = new Panel
        {
            Dock      = DockStyle.Left,
            BackColor = ThemeHelper.Accent,
            Width     = 0,
        };
        _pnlCapacityBar = new Panel
        {
            Dock      = DockStyle.Bottom,
            Height    = 6,
            BackColor = ThemeHelper.Border,
        };
        _pnlCapacityBar.Controls.Add(_pnlCapacityFill);

        capPanel.Controls.Add(_pnlCapacityBar);
        capPanel.Controls.Add(_lblCapacity);
        card.Controls.Add(capPanel);

        // Wire events
        _dtpDelivery.ValueChanged    += DtpDelivery_ValueChanged;
        _chkNoDeadline.CheckedChanged += ChkNoDeadline_CheckedChanged;
        _nudWorkingDays.ValueChanged  += (_, _) => UpdateCapacity();
        _nudTeamSize.ValueChanged     += (_, _) => UpdateCapacity();
        _chkHasLeader.CheckedChanged  += (_, _) => UpdateCapacity();
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
            _dtpDelivery.Value = _state.DeliveryDate.Value;
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
        state.DeliveryDate  = _chkNoDeadline.Checked ? null : _dtpDelivery.Value.Date;
        state.WorkingDays   = (int)_nudWorkingDays.Value;
        state.TeamSize      = (int)_nudTeamSize.Value;
        state.HasLeader     = _chkHasLeader.Checked;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static NumericUpDown MakeNud(
        Panel parent, int y,
        decimal min, decimal max, decimal defaultVal,
        int width = 120)
    {
        var nud = new NumericUpDown
        {
            Location    = new Point(16, y),
            Width       = width,
            Minimum     = min,
            Maximum     = max,
            Value       = defaultVal,
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font        = new Font("Segoe UI", 10f),
            TextAlign   = HorizontalAlignment.Center,
        };
        parent.Controls.Add(nud);
        return nud;
    }

    private static void AddSectionLabel(Panel parent, string text, ref int y)
    {
        var lbl = new Label
        {
            Text      = text,
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),
            AutoSize  = true,
        };
        parent.Controls.Add(lbl);
        y += 26;

        var line = new Panel
        {
            BackColor = ThemeHelper.Border,
            Location  = new Point(16, y),
            Size      = new Size(480, 1),
        };
        parent.Controls.Add(line);
        y += 10;
    }

    private static void AddFieldLabel(Panel parent, string text, int y)
    {
        parent.Controls.Add(new Label
        {
            Text      = text,
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Location  = new Point(16, y),
            AutoSize  = true,
        });
    }

    private static int CountWorkingDays(DateTime start, DateTime end)
    {
        if (end <= start) return 1;
        int days = 0;
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
