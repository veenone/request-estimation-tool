using EstimationTool.Services;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step5PrFixes : UserControl
{
    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly WizardPanel.WizardState _state;

    private NumericUpDown _nudSimple  = null!;
    private NumericUpDown _nudMedium  = null!;
    private NumericUpDown _nudComplex = null!;
    private Label         _lblTotal   = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step5PrFixes(WizardPanel.WizardState state)
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
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 340));  // form
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // filler
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(layout);

        // Header
        var lblHeader = new Label
        {
            Text = "Step 5: PR Fix Estimation",
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
            Width = 460,
            Height = 330,
            Anchor = AnchorStyles.Top | AnchorStyles.Left,
        };
        ThemeHelper.StylePanel(card);

        int y = 16;

        var lblIntro = new Label
        {
            Text = "Estimate the number of PRs/defects expected by complexity.\r\n" +
                   "These add remediation effort to the total estimate.",
            Font = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            AutoSize = false,
            Width = 420,
            Height = 36,
            Location = new Point(16, y),
        };
        card.Controls.Add(lblIntro);
        y += 48;

        // Helper: add a PR complexity row
        void AddRow(string label, string rateText, ref NumericUpDown nudOut, ref int yPos)
        {
            var rowPanel = new Panel
            {
                Location = new Point(16, yPos),
                Width = 420,
                Height = 60,
                BackColor = ThemeHelper.Background,
            };
            ThemeHelper.StylePanel(rowPanel);

            var lbl = new Label
            {
                Text = label,
                Font = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
                ForeColor = ThemeHelper.Text,
                BackColor = Color.Transparent,
                Location = new Point(12, 8),
                AutoSize = true,
            };

            var rate = new Label
            {
                Text = rateText,
                Font = new Font("Segoe UI", 8.5f),
                ForeColor = ThemeHelper.TextSecondary,
                BackColor = Color.Transparent,
                Location = new Point(12, 28),
                AutoSize = true,
            };

            var nud = new NumericUpDown
            {
                Minimum  = 0,
                Maximum  = 100,
                Value    = 0,
                Width    = 80,
                Height   = 28,
                Location = new Point(320, 16),
                BackColor = ThemeHelper.Surface,
                ForeColor = ThemeHelper.Text,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Segoe UI", 10f),
                TextAlign = HorizontalAlignment.Center,
            };

            rowPanel.Controls.AddRange(new Control[] { lbl, rate, nud });
            card.Controls.Add(rowPanel);

            nudOut = nud;
            yPos += 70;
        }

        AddRow("Simple PRs",  "2 hours each  — minor fixes, config changes",    ref _nudSimple,  ref y);
        AddRow("Medium PRs",  "4 hours each  — moderate rework, logic changes", ref _nudMedium,  ref y);
        AddRow("Complex PRs", "8 hours each  — significant analysis + rework",  ref _nudComplex, ref y);

        y += 8;

        // Total summary
        var totalBorder = new Panel
        {
            Location = new Point(16, y),
            Width = 420,
            Height = 42,
            BackColor = ThemeHelper.Sidebar,
        };

        _lblTotal = new Label
        {
            Text = "Total PR effort:  0 h",
            Font = new Font("Segoe UI Semibold", 11f, FontStyle.Bold),
            ForeColor = ThemeHelper.Accent,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        totalBorder.Controls.Add(_lblTotal);
        card.Controls.Add(totalBorder);

        layout.Controls.Add(card, 0, 1);

        // Wire up events
        _nudSimple.ValueChanged  += (_, _) => UpdateTotal();
        _nudMedium.ValueChanged  += (_, _) => UpdateTotal();
        _nudComplex.ValueChanged += (_, _) => UpdateTotal();
    }

    // -------------------------------------------------------------------------
    // Logic
    // -------------------------------------------------------------------------

    private void UpdateTotal()
    {
        int simple  = (int)_nudSimple.Value;
        int medium  = (int)_nudMedium.Value;
        int complex = (int)_nudComplex.Value;

        double total = simple * 2.0 + medium * 4.0 + complex * 8.0;
        _lblTotal.Text = $"Total PR effort:  {total:F0} h  " +
                         $"({simple}×2h + {medium}×4h + {complex}×8h)";
    }

    private void PopulateFromState()
    {
        _nudSimple.Value  = Math.Min(_nudSimple.Maximum,  Math.Max(0, _state.PrSimple));
        _nudMedium.Value  = Math.Min(_nudMedium.Maximum,  Math.Max(0, _state.PrMedium));
        _nudComplex.Value = Math.Min(_nudComplex.Maximum, Math.Max(0, _state.PrComplex));
        UpdateTotal();
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.PrSimple  = (int)_nudSimple.Value;
        state.PrMedium  = (int)_nudMedium.Value;
        state.PrComplex = (int)_nudComplex.Value;
    }
}
