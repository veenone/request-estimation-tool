using EstimationTool.Forms.Panels.WizardSteps;
using EstimationTool.Models;
using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

public class WizardPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Nested WizardState
    // -------------------------------------------------------------------------

    public class WizardState
    {
        public int? RequestId { get; set; }
        public string ProjectName { get; set; } = "";
        public string ProjectType { get; set; } = "NEW";
        public List<int> SelectedFeatureIds { get; set; } = new();
        public List<int> NewFeatureIds { get; set; } = new();
        public List<int> ReferenceProjectIds { get; set; } = new();
        public List<int> SelectedDutIds { get; set; } = new();
        public List<int> SelectedProfileIds { get; set; } = new();
        public List<List<int>> DutProfileMatrix { get; set; } = new();
        public int PrSimple { get; set; }
        public int PrMedium { get; set; }
        public int PrComplex { get; set; }
        public DateTime? DeliveryDate { get; set; }
        public int TeamSize { get; set; } = 1;
        public bool HasLeader { get; set; }
        public int WorkingDays { get; set; } = 20;
        public string CreatedBy { get; set; } = "";
        public CalculationResult? CalcResult { get; set; }
    }

    // -------------------------------------------------------------------------
    // Step metadata
    // -------------------------------------------------------------------------

    private static readonly (string Label, string Short)[] StepMeta =
    {
        ("Project Info",   "1"),
        ("Features",       "2"),
        ("References",     "3"),
        ("DUT x Profile",  "4"),
        ("PR Fixes",       "5"),
        ("Delivery/Team",  "6"),
        ("Review",         "7"),
    };

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly MainForm _mainForm;
    private readonly WizardState _state;

    private int _currentStep;

    private readonly Panel _progressPanel;
    private readonly Panel[] _stepDots = new Panel[7];
    private readonly Label[] _stepLabels = new Label[7];

    private readonly Panel _contentPanel;
    private UserControl? _currentStepControl;

    private readonly Panel _buttonBar;
    private readonly Button _btnCancel;
    private readonly Button _btnBack;
    private readonly Button _btnNext;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public WizardPanel(BackendApiService ipc, MainForm mainForm, int? requestId = null)
    {
        _ipc = ipc;
        _mainForm = mainForm;
        _state = new WizardState { RequestId = requestId };

        Dock = DockStyle.Fill;
        BackColor = ThemeHelper.Background;
        Padding = new Padding(0);

        // --- Progress bar ---------------------------------------------------
        _progressPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 72,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(16, 0, 16, 0),
        };
        Controls.Add(_progressPanel);

        // --- Button bar (bottom) --------------------------------------------
        _buttonBar = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 56,
            BackColor = ThemeHelper.Sidebar,
            Padding = new Padding(16, 8, 16, 8),
        };

        _btnCancel = new Button { Text = "Cancel", Width = 90, Height = 36, Anchor = AnchorStyles.Left | AnchorStyles.Top };
        _btnBack   = new Button { Text = "< Back",  Width = 90, Height = 36, Anchor = AnchorStyles.Right | AnchorStyles.Top };
        _btnNext   = new Button { Text = "Next >",  Width = 110, Height = 36, Anchor = AnchorStyles.Right | AnchorStyles.Top };

        ThemeHelper.StyleButton(_btnCancel, false);
        ThemeHelper.StyleButton(_btnBack,   false);
        ThemeHelper.StyleButton(_btnNext,   true);

        _btnCancel.Location = new Point(0, 10);
        _btnNext.Location   = new Point(_buttonBar.Width - 126, 10);
        _btnBack.Location   = new Point(_buttonBar.Width - 222, 10);

        _buttonBar.Controls.AddRange(new Control[] { _btnCancel, _btnBack, _btnNext });
        _buttonBar.Resize += (_, _) =>
        {
            _btnNext.Left = _buttonBar.Width - 126;
            _btnBack.Left = _buttonBar.Width - 222;
        };
        Controls.Add(_buttonBar);

        // Build progress bar now that buttons are initialized
        BuildProgressBar();

        // --- Content area ---------------------------------------------------
        _contentPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(24, 16, 24, 16),
            AutoScroll = true,
        };
        Controls.Add(_contentPanel);

        // Wire events
        _btnCancel.Click += BtnCancel_Click;
        _btnBack.Click   += BtnBack_Click;
        _btnNext.Click   += BtnNext_Click;

        Load += (_, _) => NavigateToStep(0);
    }

    // -------------------------------------------------------------------------
    // Progress bar construction
    // -------------------------------------------------------------------------

    private void BuildProgressBar()
    {
        _progressPanel.Controls.Clear();

        // We lay out a TableLayoutPanel: 7 columns, each holding a dot + label
        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = StepMeta.Length * 2 - 1, // steps + connectors between
            RowCount = 1,
            BackColor = Color.Transparent,
        };

        // Column styles: steps are fixed-width, connectors fill
        for (int i = 0; i < table.ColumnCount; i++)
        {
            table.ColumnStyles.Add(i % 2 == 0
                ? new ColumnStyle(SizeType.Absolute, 80)
                : new ColumnStyle(SizeType.Percent, 100f / (StepMeta.Length - 1)));
        }
        table.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        for (int i = 0; i < StepMeta.Length; i++)
        {
            int colIdx = i * 2;

            var cell = new Panel
            {
                BackColor = Color.Transparent,
                Dock = DockStyle.Fill,
                Margin = new Padding(0),
            };

            // Circle dot
            var dot = new Panel
            {
                Width = 28, Height = 28,
                BackColor = ThemeHelper.Border,
                Anchor = AnchorStyles.None,
            };
            dot.Left = (80 - 28) / 2;
            dot.Top  = 10;
            dot.Paint += (sender, e) =>
            {
                var p = (Panel)sender!;
                e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
                using var brush = new SolidBrush(p.BackColor);
                e.Graphics.FillEllipse(brush, 0, 0, p.Width - 1, p.Height - 1);
            };

            // Step number inside dot
            var dotLabel = new Label
            {
                Text = StepMeta[i].Short,
                ForeColor = ThemeHelper.Text,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleCenter,
                Size = dot.Size,
                Location = new Point(0, 0),
            };
            dot.Controls.Add(dotLabel);

            // Step name label below dot
            var lbl = new Label
            {
                Text = StepMeta[i].Label,
                ForeColor = ThemeHelper.TextSecondary,
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 7.5f),
                TextAlign = ContentAlignment.TopCenter,
                AutoSize = false,
                Width = 80,
                Height = 18,
                Top = dot.Bottom + 2,
                Left = 0,
            };

            cell.Controls.Add(dot);
            cell.Controls.Add(lbl);

            _stepDots[i]   = dot;
            _stepLabels[i] = lbl;

            table.Controls.Add(cell, colIdx, 0);

            // Connector line between steps
            if (i < StepMeta.Length - 1)
            {
                var connector = new Panel
                {
                    BackColor = ThemeHelper.Border,
                    Height = 2,
                    Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
                    Dock = DockStyle.None,
                };

                var connCell = new Panel
                {
                    BackColor = Color.Transparent,
                    Dock = DockStyle.Fill,
                };
                connector.Dock = DockStyle.None;
                connector.Height = 2;
                connector.Top = 23; // vertically center with dot (10 + 14 - 1)
                connector.Left = 0;
                connector.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top;
                connCell.Controls.Add(connector);
                connCell.Resize += (_, _) => connector.Width = connCell.Width;

                table.Controls.Add(connCell, colIdx + 1, 0);
            }
        }

        _progressPanel.Controls.Add(table);
        UpdateProgressBar();
    }

    private void UpdateProgressBar()
    {
        for (int i = 0; i < StepMeta.Length; i++)
        {
            if (i < _currentStep)
            {
                _stepDots[i].BackColor = ThemeHelper.FeasibilityGreen;
                _stepLabels[i].ForeColor = ThemeHelper.FeasibilityGreen;
            }
            else if (i == _currentStep)
            {
                _stepDots[i].BackColor = ThemeHelper.Accent;
                _stepLabels[i].ForeColor = ThemeHelper.Text;
            }
            else
            {
                _stepDots[i].BackColor = ThemeHelper.Border;
                _stepLabels[i].ForeColor = ThemeHelper.TextSecondary;
            }
            _stepDots[i].Invalidate();
        }

        // Back is disabled on step 0
        _btnBack.Enabled = _currentStep > 0;

        // On the last step (Review), Next becomes "Finish" but is hidden —
        // the Review step has its own Save button.
        if (_currentStep == StepMeta.Length - 1)
        {
            _btnNext.Visible = false;
        }
        else
        {
            _btnNext.Visible = true;
            _btnNext.Text = _currentStep == StepMeta.Length - 2 ? "Review >" : "Next >";
        }
    }

    // -------------------------------------------------------------------------
    // Step navigation
    // -------------------------------------------------------------------------

    private void NavigateToStep(int step)
    {
        // Dispose previous step control
        if (_currentStepControl != null)
        {
            _contentPanel.Controls.Remove(_currentStepControl);
            _currentStepControl.Dispose();
            _currentStepControl = null;
        }

        _currentStep = step;
        UpdateProgressBar();

        _currentStepControl = step switch
        {
            0 => new Step1ProjectType(_ipc, _state),
            1 => new Step2Features(_ipc, _state),
            2 => new Step3References(_ipc, _state),
            3 => new Step4DutProfile(_ipc, _state),
            4 => new Step5PrFixes(_state),
            5 => new Step6DeliveryTeam(_state),
            6 => new Step7Review(_ipc, _state, _mainForm),
            _ => throw new InvalidOperationException($"Unknown step {step}")
        };

        _currentStepControl.Dock = DockStyle.Fill;
        _contentPanel.Controls.Add(_currentStepControl);
    }

    // -------------------------------------------------------------------------
    // Button handlers
    // -------------------------------------------------------------------------

    private void BtnCancel_Click(object? sender, EventArgs e)
    {
        var result = MessageBox.Show(
            "Are you sure you want to cancel this estimation? All unsaved changes will be lost.",
            "Cancel Estimation",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question);

        if (result == DialogResult.Yes)
        {
            _mainForm.NavigateTo("Dashboard");
        }
    }

    private void BtnBack_Click(object? sender, EventArgs e)
    {
        if (_currentStep > 0)
            NavigateToStep(_currentStep - 1);
    }

    private async void BtnNext_Click(object? sender, EventArgs e)
    {
        _btnNext.Enabled = false;
        _btnBack.Enabled = false;

        try
        {
            if (!ValidateCurrentStep())
                return;

            // Save current step data into state
            SaveCurrentStepToState();

            if (_currentStep < StepMeta.Length - 1)
                NavigateToStep(_currentStep + 1);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"An error occurred: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            _btnNext.Enabled = true;
            _btnBack.Enabled = _currentStep > 0;
        }

        await Task.CompletedTask;
    }

    // -------------------------------------------------------------------------
    // Validation & state saving — delegates to current step control
    // -------------------------------------------------------------------------

    private bool ValidateCurrentStep()
    {
        return _currentStepControl switch
        {
            Step1ProjectType s1 => s1.Validate(out string err1) || ShowError(err1),
            Step2Features    s2 => s2.Validate(out string err2) || ShowError(err2),
            Step3References  _  => true, // optional step
            Step4DutProfile  s4 => s4.Validate(out string err4) || ShowError(err4),
            Step5PrFixes     _  => true,
            Step6DeliveryTeam s6 => s6.Validate(out string err6) || ShowError(err6),
            Step7Review      _  => true,
            _ => true
        };
    }

    private void SaveCurrentStepToState()
    {
        switch (_currentStepControl)
        {
            case Step1ProjectType s1: s1.SaveToState(_state); break;
            case Step2Features    s2: s2.SaveToState(_state); break;
            case Step3References  s3: s3.SaveToState(_state); break;
            case Step4DutProfile  s4: s4.SaveToState(_state); break;
            case Step5PrFixes     s5: s5.SaveToState(_state); break;
            case Step6DeliveryTeam s6: s6.SaveToState(_state); break;
        }
    }

    private static bool ShowError(string message)
    {
        if (!string.IsNullOrWhiteSpace(message))
            MessageBox.Show(message, "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        return false;
    }
}
