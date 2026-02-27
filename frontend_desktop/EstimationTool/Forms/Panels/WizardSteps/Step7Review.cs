using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;
using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public class Step7Review : UserControl
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

    // UI regions
    private Button _btnCalculate = null!;
    private Panel  _pnlLoading   = null!;
    private Panel  _pnlResults   = null!;

    // Summary cards
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

    // Action buttons
    private Button _btnSaveDraft  = null!;
    private Button _btnExcel      = null!;
    private Button _btnWord       = null!;
    private Button _btnPdf        = null!;
    private Panel  _pnlActions    = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step7Review(BackendApiService ipc, WizardPanel.WizardState state, MainForm mainForm)
    {
        _ipc      = ipc;
        _state    = state;
        _mainForm = mainForm;

        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        BuildUI();

        // If we already have a prior calculation in state (back-nav), re-render
        if (_state.CalcResult != null)
            RenderResults(_state.CalcResult);
    }

    // -------------------------------------------------------------------------
    // UI construction
    // -------------------------------------------------------------------------

    private void BuildUI()
    {
        var outer = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 4,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        outer.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        outer.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));   // calculate button + loading
        outer.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // results
        outer.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));   // action buttons
        outer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        Controls.Add(outer);

        // Row 0: Header
        var lblHeader = new Label
        {
            Text = "Step 7: Review & Calculate",
            Font = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        outer.Controls.Add(lblHeader, 0, 0);

        // Row 1: Calculate button + loading indicator
        var calcRow = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
        };

        _btnCalculate = new Button
        {
            Text     = "Calculate Estimation",
            Width    = 200,
            Height   = 40,
            Location = new Point(0, 10),
            Font     = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
        };
        ThemeHelper.StyleButton(_btnCalculate, true);
        _btnCalculate.Click += BtnCalculate_Click;
        calcRow.Controls.Add(_btnCalculate);

        _pnlLoading = new Panel
        {
            Location  = new Point(216, 10),
            Width     = 280,
            Height    = 40,
            BackColor = Color.Transparent,
            Visible   = false,
        };
        var lblLoading = new Label
        {
            Text      = "Calculating, please wait...",
            Font      = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _pnlLoading.Controls.Add(lblLoading);
        calcRow.Controls.Add(_pnlLoading);
        outer.Controls.Add(calcRow, 0, 1);

        // Row 2: Results panel (scrollable)
        _pnlResults = new Panel
        {
            Dock       = DockStyle.Fill,
            BackColor  = ThemeHelper.Background,
            AutoScroll = true,
            Visible    = false,
        };
        BuildResultsPanel();
        outer.Controls.Add(_pnlResults, 0, 2);

        // Row 3: Action buttons
        _pnlActions = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding   = new Padding(0, 8, 0, 8),
            Visible   = false,
        };
        BuildActionButtons();
        outer.Controls.Add(_pnlActions, 0, 3);
    }

    private void BuildResultsPanel()
    {
        int y = 8;

        // --- Summary cards row -------------------------------------------
        var cardsPanel = new TableLayoutPanel
        {
            Location    = new Point(0, y),
            Height      = 90,
            ColumnCount = 7,
            RowCount    = 1,
            BackColor   = ThemeHelper.Background,
            Anchor      = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        for (int i = 0; i < 7; i++)
            cardsPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / 7));
        cardsPanel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        _pnlResults.Controls.Add(cardsPanel);
        _pnlResults.Resize += (_, _) => cardsPanel.Width = _pnlResults.ClientSize.Width - 2;

        Panel MakeCard(string title, out Label valLabel)
        {
            var card = ThemeHelper.CreateMetricCard(title, "—");
            // Extract the value label (second control added = Fill docked)
            valLabel = (Label)card.Controls[0]; // Fill control is index 0 after Controls.Add order
            return card;
        }

        var cardTester  = ThemeHelper.CreateMetricCard("Tester Hours",   "—");
        var cardLeader  = ThemeHelper.CreateMetricCard("Leader Hours",   "—");
        var cardPr      = ThemeHelper.CreateMetricCard("PR Fix Hours",   "—");
        var cardStudy   = ThemeHelper.CreateMetricCard("Study Hours",    "—");
        var cardBuffer  = ThemeHelper.CreateMetricCard("Buffer Hours",   "—");
        var cardTotal   = ThemeHelper.CreateMetricCard("Grand Total (h)","—", ThemeHelper.Accent);
        var cardDays    = ThemeHelper.CreateMetricCard("Grand Total (d)","—", ThemeHelper.Accent);

        // The metric label is the Fill-docked control (index 0 in controls after createMetricCard)
        _lblTesterHours = (Label)cardTester.Controls[0];
        _lblLeaderHours = (Label)cardLeader.Controls[0];
        _lblPrHours     = (Label)cardPr.Controls[0];
        _lblStudyHours  = (Label)cardStudy.Controls[0];
        _lblBufferHours = (Label)cardBuffer.Controls[0];
        _lblGrandTotal  = (Label)cardTotal.Controls[0];
        _lblGrandDays   = (Label)cardDays.Controls[0];

        cardsPanel.Controls.Add(WrapInPadding(cardTester), 0, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardLeader), 1, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardPr),     2, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardStudy),  3, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardBuffer), 4, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardTotal),  5, 0);
        cardsPanel.Controls.Add(WrapInPadding(cardDays),   6, 0);

        y += 98;

        // --- Feasibility + utilisation row --------------------------------
        var feasRow = new Panel
        {
            Location  = new Point(0, y),
            Height    = 48,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            BackColor = ThemeHelper.Sidebar,
        };
        _pnlResults.Controls.Add(feasRow);
        _pnlResults.Resize += (_, _) => feasRow.Width = _pnlResults.ClientSize.Width - 2;

        // Feasibility badge
        _pnlFeasBadge = new Panel
        {
            Location  = new Point(12, 10),
            Width     = 130,
            Height    = 28,
            BackColor = ThemeHelper.Border,
        };
        _lblFeasText = new Label
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleCenter,
        };
        _pnlFeasBadge.Controls.Add(_lblFeasText);
        feasRow.Controls.Add(_pnlFeasBadge);

        // Utilisation text
        _lblUtilization = new Label
        {
            Location  = new Point(156, 0),
            Width     = 280,
            Height    = 48,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        feasRow.Controls.Add(_lblUtilization);

        // Capacity text
        _lblCapacity = new Label
        {
            Location  = new Point(448, 0),
            Width     = 280,
            Height    = 48,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        feasRow.Controls.Add(_lblCapacity);

        y += 56;

        // Utilisation bar
        _pnlUtilBg = new Panel
        {
            Location  = new Point(0, y),
            Height    = 6,
            BackColor = ThemeHelper.Border,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        _pnlUtilFill = new Panel
        {
            Dock      = DockStyle.Left,
            Width     = 0,
            BackColor = ThemeHelper.Accent,
        };
        _pnlUtilBg.Controls.Add(_pnlUtilFill);
        _pnlResults.Controls.Add(_pnlUtilBg);
        _pnlResults.Resize += (_, _) => _pnlUtilBg.Width = _pnlResults.ClientSize.Width - 2;
        y += 14;

        // --- Risk flags ---------------------------------------------------
        var lblRisks = new Label
        {
            Text      = "Risk Flags",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(0, y),
            AutoSize  = true,
        };
        _pnlResults.Controls.Add(lblRisks);
        y += 24;

        _pnlRisks = new FlowLayoutPanel
        {
            Location  = new Point(0, y),
            Height    = 36,
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            BackColor = ThemeHelper.Background,
            WrapContents = false,
            AutoSize  = false,
        };
        _pnlResults.Controls.Add(_pnlRisks);
        _pnlResults.Resize += (_, _) => _pnlRisks.Width = _pnlResults.ClientSize.Width - 2;
        y += 44;

        // --- Task breakdown -----------------------------------------------
        var lblTasks = new Label
        {
            Text      = "Task Breakdown",
            Font      = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Location  = new Point(0, y),
            AutoSize  = true,
        };
        _pnlResults.Controls.Add(lblTasks);
        y += 24;

        _dgvTasks = new DataGridView
        {
            Location  = new Point(0, y),
            Anchor    = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top | AnchorStyles.Bottom,
            Height    = 300,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            ReadOnly  = true,
        };
        ThemeHelper.StyleDataGridView(_dgvTasks);
        _dgvTasks.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.None;

        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Task Name",
            Name       = "Name",
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 140,
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Type", Name = "Type", Width = 80,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Base Hours", Name = "Base", Width = 82,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "DUT Mult.", Name = "DutMult", Width = 76,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Profile Mult.", Name = "ProfMult", Width = 84,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Complexity", Name = "Complexity", Width = 80,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        });
        _dgvTasks.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Calculated (h)", Name = "Calc", Width = 100,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight,
                                 Font = new Font("Segoe UI", 9f, FontStyle.Bold) },
        });

        _pnlResults.Controls.Add(_dgvTasks);
        _pnlResults.Resize += (_, _) =>
        {
            _dgvTasks.Width = _pnlResults.ClientSize.Width - 2;
            _dgvTasks.Height = Math.Max(150, _pnlResults.ClientSize.Height - y - 8);
        };

        _pnlResults.AutoScrollMinSize = new Size(0, y + 320);
    }

    private void BuildActionButtons()
    {
        _btnSaveDraft = new Button
        {
            Text     = "Save as Draft",
            Width    = 130,
            Height   = 36,
            Location = new Point(0, 8),
            Font     = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
        };
        ThemeHelper.StyleButton(_btnSaveDraft, true);
        _btnSaveDraft.Click += BtnSaveDraft_Click;
        _pnlActions.Controls.Add(_btnSaveDraft);

        var sep = new Label
        {
            Text      = "|",
            ForeColor = ThemeHelper.Border,
            BackColor = Color.Transparent,
            AutoSize  = true,
            Location  = new Point(140, 16),
            Font      = new Font("Segoe UI", 9f),
        };
        _pnlActions.Controls.Add(sep);

        _btnExcel = MakeReportButton("Download Excel", 160);
        _btnWord  = MakeReportButton("Download Word",  290);
        _btnPdf   = MakeReportButton("Download PDF",   420);

        _btnExcel.Click += async (_, _) => await DownloadReportAsync("xlsx", "Excel Workbook|*.xlsx");
        _btnWord.Click  += async (_, _) => await DownloadReportAsync("docx", "Word Document|*.docx");
        _btnPdf.Click   += async (_, _) => await DownloadReportAsync("pdf",  "PDF Document|*.pdf");

        _pnlActions.Controls.AddRange(new Control[] { _btnExcel, _btnWord, _btnPdf });
    }

    private Button MakeReportButton(string text, int x)
    {
        var btn = new Button
        {
            Text     = text,
            Width    = 120,
            Height   = 36,
            Location = new Point(x, 8),
        };
        ThemeHelper.StyleButton(btn, false);
        return btn;
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

            _state.CalcResult   = result;
            _savedEstimationId  = null; // new calculation — require re-save

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

            _btnSaveDraft.Text    = $"Saved  ({resp.EstimationNumber ?? $"#{resp.Id}"})";
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

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Panel WrapInPadding(Panel card)
    {
        var wrapper = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding   = new Padding(3),
        };
        card.Dock = DockStyle.Fill;
        wrapper.Controls.Add(card);
        return wrapper;
    }
}
