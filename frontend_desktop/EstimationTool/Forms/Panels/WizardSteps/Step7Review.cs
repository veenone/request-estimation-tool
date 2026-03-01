using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step7Review : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrappers
    // -------------------------------------------------------------------------

    private class SaveResponse
    {
        [JsonPropertyName("id")]                 public int    Id               { get; set; }
        [JsonPropertyName("estimation_number")]  public string? EstimationNumber { get; set; }
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly WizardPanel.WizardState _state;
    private readonly MainForm _mainForm;

    private int? _savedEstimationId;

    // UI regions (declared in Designer InitializeComponent)
    private Button _btnCalculate = null!;

    // Summary card value labels (extracted from metric cards in Designer)
    private Label _lblTesterHours  = null!;
    private Label _lblLeaderHours  = null!;
    private Label _lblPrHours      = null!;
    private Label _lblStudyHours   = null!;
    private Label _lblBufferHours  = null!;
    private Label _lblGrandTotal   = null!;
    private Label _lblGrandDays    = null!;
    private Label _lblCapacity     = null!;
    private Label _lblUtilization  = null!;

    // Feasibility badge
    private Panel _pnlFeasBadge   = null!;
    private Label _lblFeasText    = null!;

    // Utilisation bar
    private Panel _pnlUtilBg      = null!;
    private Panel _pnlUtilFill    = null!;

    // Risk flags
    private FlowLayoutPanel _pnlRisks = null!;

    // Task breakdown grid
    private DataGridView _dgvTasks = null!;

    // Action buttons (declared in Designer InitializeComponent)
    private Button _btnSaveDraft  = null!;
    private Button _btnExcel      = null!;
    private Button _btnWord       = null!;
    private Button _btnPdf        = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step7Review(BackendApiService ipc, WizardPanel.WizardState state, MainForm mainForm)
    {
        _ipc      = ipc;
        _state    = state;
        _mainForm = mainForm;

        InitializeComponent();

        // Wire event handlers for controls declared in the Designer
        _btnCalculate.Click += BtnCalculate_Click;
        _btnSaveDraft.Click += BtnSaveDraft_Click;

        _btnExcel.Click += async (_, _) => await DownloadReportAsync("xlsx", "Excel Workbook|*.xlsx");
        _btnWord.Click  += async (_, _) => await DownloadReportAsync("docx", "Word Document|*.docx");
        _btnPdf.Click   += async (_, _) => await DownloadReportAsync("pdf",  "PDF Document|*.pdf");

        // If we already have a prior calculation in state (back-nav), re-render
        if (_state.CalcResult != null)
            RenderResults(_state.CalcResult);
    }

    // -------------------------------------------------------------------------
    // Calculate
    // -------------------------------------------------------------------------

    private async void BtnCalculate_Click(object? sender, EventArgs e)
    {
        _btnCalculate.Enabled = false;
        _pnlLoading.Visible   = true;
        _pnlResults.Visible   = false;
        _pnlActions.Visible   = false;

        try
        {
            var payload = new
            {
                project_type        = _state.ProjectType,
                features            = _state.SelectedFeatureIds,
                new_features        = _state.NewFeatureIds,
                dut_ids             = _state.SelectedDutIds,
                profile_ids         = _state.SelectedProfileIds,
                dut_profile_matrix  = _state.DutProfileMatrix,
                pr_fixes            = new
                {
                    simple  = _state.PrSimple,
                    medium  = _state.PrMedium,
                    complex = _state.PrComplex,
                },
                reference_project_ids = _state.ReferenceProjectIds,
                team_size           = _state.TeamSize,
                has_leader          = _state.HasLeader,
                working_days        = _state.WorkingDays,
                delivery_date       = _state.DeliveryDate?.ToString("yyyy-MM-dd"),
            };

            var result = await _ipc.SendCommandAsync<CalculationResult>("calculate_estimation", payload);

            _state.CalcResult  = result;
            _savedEstimationId = null; // new calculation — require re-save

            RenderResults(result);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Calculation failed:\n{ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            _btnCalculate.Enabled = true;
            _pnlLoading.Visible   = false;
        }
    }

    // -------------------------------------------------------------------------
    // Render results
    // -------------------------------------------------------------------------

    private void RenderResults(CalculationResult r)
    {
        // Summary cards
        _lblTesterHours.Text = $"{r.TotalTesterHours:F0}";
        _lblLeaderHours.Text = $"{r.TotalLeaderHours:F0}";
        _lblPrHours.Text     = $"{r.PrFixHours:F0}";
        _lblStudyHours.Text  = $"{r.StudyHours:F0}";
        _lblBufferHours.Text = $"{r.BufferHours:F0}";
        _lblGrandTotal.Text  = $"{r.GrandTotalHours:F1}";
        _lblGrandDays.Text   = $"{r.GrandTotalDays:F1}";

        // Feasibility badge
        _pnlFeasBadge.BackColor = ThemeHelper.GetFeasibilityColor(r.FeasibilityStatus);
        _lblFeasText.Text = r.FeasibilityStatus.Replace('_', ' ');

        // Utilisation
        _lblUtilization.Text = $"Utilisation:  {r.UtilizationPct:F1}%  " +
                               $"({r.GrandTotalHours:F0} h / {r.CapacityHours:F0} h)";
        _lblUtilization.ForeColor = ThemeHelper.GetFeasibilityColor(r.FeasibilityStatus);

        _lblCapacity.Text = $"Team capacity:  {r.CapacityHours:F0} h";

        // Utilisation bar fill
        double utilFraction = r.CapacityHours > 0
            ? Math.Min(1.0, r.GrandTotalHours / r.CapacityHours)
            : 0;

        _pnlUtilBg.Resize += (_, _) =>
            _pnlUtilFill.Width = (int)(_pnlUtilBg.Width * utilFraction);
        _pnlUtilFill.Width = (int)(_pnlUtilBg.Width * utilFraction);
        _pnlUtilFill.BackColor = ThemeHelper.GetFeasibilityColor(r.FeasibilityStatus);

        // Risk flags
        _pnlRisks.Controls.Clear();
        var messages = r.RiskMessages.Count > 0 ? r.RiskMessages : r.RiskFlags;
        if (messages.Count == 0)
        {
            _pnlRisks.Controls.Add(new Label
            {
                Text      = "No risk flags",
                Font      = new Font("Segoe UI", 8.5f),
                ForeColor = ThemeHelper.FeasibilityGreen,
                BackColor = Color.Transparent,
                AutoSize  = true,
            });
        }
        else
        {
            foreach (var msg in messages)
            {
                var chip = new Label
                {
                    Text      = $"  {msg}  ",
                    Font      = new Font("Segoe UI", 8.5f),
                    ForeColor = ThemeHelper.Text,
                    BackColor = ThemeHelper.FeasibilityAmber,
                    AutoSize  = true,
                    Margin    = new Padding(0, 0, 6, 0),
                    Padding   = new Padding(4, 2, 4, 2),
                    TextAlign = ContentAlignment.MiddleLeft,
                };
                _pnlRisks.Controls.Add(chip);
            }
        }

        // Task breakdown grid
        _dgvTasks.Rows.Clear();
        foreach (var task in r.Tasks)
        {
            int idx = _dgvTasks.Rows.Add(
                task.Name,
                task.TaskType,
                $"{task.BaseHours:F1}",
                $"{task.DutMultiplier:F2}x",
                $"{task.ProfileMultiplier:F2}x",
                $"{task.ComplexityWeight:F2}x",
                $"{task.CalculatedHours:F1}");

            if (task.IsNewFeatureStudy)
                _dgvTasks.Rows[idx].DefaultCellStyle.ForeColor = ThemeHelper.FeasibilityAmber;
        }

        _pnlResults.Visible = true;
        _pnlActions.Visible = true;

        // Re-enable save button (new calculation, needs saving)
        _btnSaveDraft.Enabled = true;
        _btnSaveDraft.Text    = "Save as Draft";
    }

    // -------------------------------------------------------------------------
    // Save as Draft
    // -------------------------------------------------------------------------

    private async void BtnSaveDraft_Click(object? sender, EventArgs e)
    {
        _btnSaveDraft.Enabled = false;
        _btnSaveDraft.Text    = "Saving...";

        try
        {
            var payload = new
            {
                request_id            = _state.RequestId,
                project_name          = _state.ProjectName,
                project_type          = _state.ProjectType,
                feature_ids           = _state.SelectedFeatureIds,
                new_feature_ids       = _state.NewFeatureIds,
                reference_project_ids = _state.ReferenceProjectIds,
                dut_ids               = _state.SelectedDutIds,
                profile_ids           = _state.SelectedProfileIds,
                dut_profile_matrix    = _state.DutProfileMatrix,
                pr_fixes              = new
                {
                    simple  = _state.PrSimple,
                    medium  = _state.PrMedium,
                    complex = _state.PrComplex,
                },
                team_size         = _state.TeamSize,
                has_leader        = _state.HasLeader,
                working_days      = _state.WorkingDays,
                expected_delivery = _state.DeliveryDate?.ToString("yyyy-MM-dd"),
                created_by        = _state.CreatedBy,
            };

            var resp = await _ipc.SendCommandAsync<SaveResponse>("create_estimation", payload);
            _savedEstimationId = resp.Id;

            _btnSaveDraft.Text      = $"Saved  ({resp.EstimationNumber ?? $"#{resp.Id}"})";
            _btnSaveDraft.BackColor = ThemeHelper.FeasibilityGreen;

            // Enable report download buttons now that we have an ID
            _btnExcel.Enabled = true;
            _btnWord.Enabled  = true;
            _btnPdf.Enabled   = true;

            // Navigate to detail view
            _mainForm.NavigateTo("EstimationDetail", resp.Id);
        }
        catch (Exception ex)
        {
            _btnSaveDraft.Enabled = true;
            _btnSaveDraft.Text    = "Save as Draft";
            MessageBox.Show($"Save failed:\n{ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Report download
    // -------------------------------------------------------------------------

    private async Task DownloadReportAsync(string format, string fileFilter)
    {
        if (_savedEstimationId == null)
        {
            MessageBox.Show("Please save the estimation as a draft first.",
                "Not Saved", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var btn = format switch
        {
            "xlsx" => _btnExcel,
            "docx" => _btnWord,
            _      => _btnPdf,
        };

        btn.Enabled = false;
        btn.Text    = "Generating...";

        try
        {
            var reportResult = await _ipc.SendCommandAsync<ReportResult>(
                "generate_report",
                new { id = _savedEstimationId.Value, format });

            var bytes = Convert.FromBase64String(reportResult.ContentBase64);

            using var dlg = new SaveFileDialog
            {
                Title      = "Save Report",
                Filter     = fileFilter,
                FileName   = reportResult.Filename,
                DefaultExt = format,
            };

            if (dlg.ShowDialog() == DialogResult.OK)
            {
                File.WriteAllBytes(dlg.FileName, bytes);
                MessageBox.Show($"Report saved to:\n{dlg.FileName}",
                    "Download Complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Report generation failed:\n{ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            btn.Enabled = true;
            btn.Text = format switch
            {
                "xlsx" => "Download Excel",
                "docx" => "Download Word",
                _      => "Download PDF",
            };
        }
    }
}
