using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Displays the full detail view for a single estimation: header info, effort
/// summary cards, status workflow controls, task breakdown grid, and report
/// download buttons. All UI components are declared in the Designer file.
/// </summary>
public sealed partial class EstimationDetailPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response type for the estimation picker
    // -------------------------------------------------------------------------

    private sealed class EstimationsListResponse
    {
        [JsonPropertyName("estimations")]
        public List<EstimationSummary> Estimations { get; set; } = new();
    }

    private sealed class EstimationSummary
    {
        [JsonPropertyName("id")]                 public int     Id               { get; set; }
        [JsonPropertyName("estimation_number")]  public string? EstimationNumber { get; set; }
        [JsonPropertyName("project_name")]       public string  ProjectName      { get; set; } = "";
        [JsonPropertyName("status")]             public string  Status           { get; set; } = "";
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly MainForm _mainForm;
    private int _estimationId;

    // Picker controls (shown when opened from sidebar with no specific ID)
    private Panel? _pickerPanel;
    private ComboBox? _cboEstimation;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public EstimationDetailPanel(BackendApiService ipc, MainForm mainForm, int estimationId)
    {
        _ipc = ipc;
        _mainForm = mainForm;
        _estimationId = estimationId;

        InitializeComponent();

        // Wire event handlers after InitializeComponent creates the controls
        _btnBack.Click  += (_, _) => _mainForm.NavigateTo("Dashboard");
        _btnExcel.Click += async (_, _) => await DownloadReportAsync("xlsx", "Excel Files|*.xlsx");
        _btnWord.Click  += async (_, _) => await DownloadReportAsync("docx", "Word Documents|*.docx");
        _btnPdf.Click   += async (_, _) => await DownloadReportAsync("pdf",  "PDF Files|*.pdf");
        _dgvTasks.CellFormatting += DgvTasks_CellFormatting;

        // If opened from sidebar (no specific estimation), show a picker
        if (_estimationId == 0)
            BuildEstimationPicker();

        HandleCreated += async (_, _) =>
        {
            if (_estimationId == 0)
                await LoadEstimationListAsync();
            else
                await LoadDataAsync();
        };
    }

    // -------------------------------------------------------------------------
    // Estimation picker (shown when navigated from sidebar)
    // -------------------------------------------------------------------------

    private void BuildEstimationPicker()
    {
        _pickerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 50,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 8, 0, 8),
        };

        var lbl = new Label
        {
            Text = "Select estimation:",
            Dock = DockStyle.Left,
            Width = 130,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 10f),
            TextAlign = ContentAlignment.MiddleLeft,
        };

        _cboEstimation = new ComboBox
        {
            Dock = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font("Segoe UI", 10f),
        };
        ThemeHelper.StyleComboBox(_cboEstimation);
        _cboEstimation.SelectedIndexChanged += async (_, _) =>
        {
            if (_cboEstimation.SelectedItem is EstimationComboItem item)
            {
                _estimationId = item.Id;
                await LoadDataAsync();
            }
        };

        _pickerPanel.Controls.Add(_cboEstimation);
        _pickerPanel.Controls.Add(lbl);

        // Insert picker at top of scroll area
        _scrollOuter.Controls.Add(_pickerPanel);
        _pickerPanel.BringToFront();
    }

    private async Task LoadEstimationListAsync()
    {
        try
        {
            var response = await _ipc.SendCommandAsync<EstimationsListResponse>("get_estimations");
            if (IsDisposed || _cboEstimation is null) return;

            Action populate = () =>
            {
                if (IsDisposed) return;
                _cboEstimation.Items.Clear();
                foreach (var e in response.Estimations)
                {
                    var display = $"{e.EstimationNumber ?? $"EST-{e.Id}"} — {e.ProjectName} [{e.Status}]";
                    _cboEstimation.Items.Add(new EstimationComboItem(e.Id, display));
                }
                if (_cboEstimation.Items.Count > 0)
                    _cboEstimation.SelectedIndex = 0;
            };

            if (InvokeRequired) BeginInvoke(populate); else populate();
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            Action showErr = () => ShowLoadError(ex.Message);
            if (InvokeRequired) BeginInvoke(showErr); else showErr();
        }
    }

    private sealed class EstimationComboItem(int id, string display)
    {
        public int Id { get; } = id;
        public override string ToString() => display;
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var estimation = await _ipc.SendCommandAsync<Estimation>(
                "get_estimation", new { id = _estimationId });

            if (IsDisposed) return;

            Action update = () =>
            {
                if (IsDisposed) return;
                PopulateHeader(estimation);
                PopulateInfoGrid(estimation);
                PopulateEffortCards(estimation);
                RebuildWorkflowPanel(estimation);
                PopulateTasksGrid(estimation.Tasks);
            };

            if (InvokeRequired)
                BeginInvoke(update);
            else
                update();
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            Action showErr = () => ShowLoadError(ex.Message);
            if (InvokeRequired)
                BeginInvoke(showErr);
            else
                showErr();
        }
    }

    private void PopulateHeader(Estimation e)
    {
        _lblTitle.Text = $"{e.EstimationNumber ?? $"EST-{e.Id}"} — {e.ProjectName}";

        _lblStatusBadge.Text = e.Status;
        _lblStatusBadge.ForeColor = ThemeHelper.GetStatusColor(e.Status);
        _lblStatusBadge.BackColor = Color.FromArgb(30,
            ThemeHelper.GetStatusColor(e.Status).R,
            ThemeHelper.GetStatusColor(e.Status).G,
            ThemeHelper.GetStatusColor(e.Status).B);
    }

    private void PopulateInfoGrid(Estimation e)
    {
        _lblProjectType.Text  = e.ProjectType;
        _lblDutCount.Text     = e.DutCount.ToString();
        _lblProfileCount.Text = e.ProfileCount.ToString();
        _lblCombinations.Text = e.DutProfileCombinations.ToString();
        _lblPrFixCount.Text   = e.PrFixCount.ToString();
        _lblDelivery.Text     = e.ExpectedDelivery ?? "—";
        _lblCreatedBy.Text    = e.CreatedBy ?? "—";
        _lblCreatedAt.Text    = e.CreatedAt ?? "—";
        _lblAssignedTo.Text   = e.AssignedToName ?? "Unassigned";
    }

    private void PopulateEffortCards(Estimation e)
    {
        _lblTesterHours.Text = e.TotalTesterHours.ToString("F1");
        _lblLeaderHours.Text = e.TotalLeaderHours.ToString("F1");
        _lblGrandHours.Text  = e.GrandTotalHours.ToString("F1");
        _lblGrandDays.Text   = e.GrandTotalDays.ToString("F1");
        _lblFeasibility.Text = e.FeasibilityStatus;
        _lblFeasibility.ForeColor = ThemeHelper.GetFeasibilityColor(e.FeasibilityStatus);
    }

    private void PopulateTasksGrid(List<EstimationTask> tasks)
    {
        _dgvTasks.Rows.Clear();
        foreach (var t in tasks)
        {
            _dgvTasks.Rows.Add(
                t.TaskName,
                t.TaskType,
                t.BaseHours.ToString("F1"),
                t.CalculatedHours.ToString("F1"),
                t.LeaderHours.ToString("F1"),
                t.IsNewFeatureStudy ? "Yes" : "No"
            );
        }
    }

    // -------------------------------------------------------------------------
    // Status workflow panel
    // -------------------------------------------------------------------------

    /// <summary>
    /// Clears and rebuilds the workflow panel according to the current status.
    /// </summary>
    private void RebuildWorkflowPanel(Estimation estimation)
    {
        _workflowPanel.Controls.Clear();

        var currentStatusLabel = new Label
        {
            Text = $"Status: {estimation.Status}",
            Dock = DockStyle.Top,
            Height = 26,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.GetStatusColor(estimation.Status),
            Font = new Font("Segoe UI Semibold", 10f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(0, 4, 0, 0),
        };
        _workflowPanel.Controls.Add(currentStatusLabel);

        // Approved-by text box — only shown for FINAL → APPROVED transition
        var approvedByBox = new TextBox
        {
            PlaceholderText = "Approver name...",
            Width = 180,
            Visible = false,
        };
        ThemeHelper.StyleTextBox(approvedByBox);

        var buttonsFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            Height = 40,
            BackColor = Color.Transparent,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0),
        };

        switch (estimation.Status.ToUpperInvariant())
        {
            case "DRAFT":
                AddWorkflowButton(buttonsFlow, "Mark as Final", isPrimary: true,
                    onClick: async () => await UpdateStatusAsync("FINAL", null));
                AddWorkflowButton(buttonsFlow, "Revise",
                    onClick: async () => await UpdateStatusAsync("REVISED", null));
                break;

            case "FINAL":
                approvedByBox.Visible = true;
                AddWorkflowButton(buttonsFlow, "Approve", isPrimary: true, onClick: async () =>
                {
                    var approver = approvedByBox.Text.Trim();
                    if (string.IsNullOrEmpty(approver))
                    {
                        MessageBox.Show("Please enter the approver name.", "Validation",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        return;
                    }
                    await UpdateStatusAsync("APPROVED", approver);
                });
                AddWorkflowButton(buttonsFlow, "Revise",
                    onClick: async () => await UpdateStatusAsync("REVISED", null));
                break;

            case "APPROVED":
                AddWorkflowButton(buttonsFlow, "Revise",
                    onClick: async () => await UpdateStatusAsync("REVISED", null));
                break;

            case "REVISED":
                AddWorkflowButton(buttonsFlow, "Back to Draft", isPrimary: true,
                    onClick: async () => await UpdateStatusAsync("DRAFT", null));
                break;
        }

        // Export button — visible for FINAL/APPROVED estimations linked to external systems
        bool canExport = estimation.Status is "FINAL" or "APPROVED"
            && !string.IsNullOrEmpty(estimation.ExternalId)
            && estimation.RequestSource is not null and not "MANUAL";
        if (canExport)
        {
            var sourceName = estimation.RequestSource!;
            AddWorkflowButton(buttonsFlow, $"Export to {sourceName[0]}{sourceName[1..].ToLower()}",
                onClick: async () => await ExportToExternalAsync());
        }

        _workflowPanel.Controls.Add(buttonsFlow);

        if (approvedByBox.Visible)
        {
            var approvedByPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 34,
                BackColor = Color.Transparent,
                Padding = new Padding(0, 4, 0, 0),
            };
            var approvedByLabel = new Label
            {
                Text = "Approved By:",
                AutoSize = true,
                ForeColor = ThemeHelper.TextSecondary,
                Font = new Font("Segoe UI", 9f),
                Dock = DockStyle.Left,
                TextAlign = ContentAlignment.MiddleLeft,
                Width = 90,
            };
            approvedByBox.Dock = DockStyle.Left;
            approvedByPanel.Controls.Add(approvedByBox);
            approvedByPanel.Controls.Add(approvedByLabel);
            _workflowPanel.Controls.Add(approvedByPanel);
        }
    }

    private static void AddWorkflowButton(
        FlowLayoutPanel container,
        string text,
        bool isPrimary = false,
        Func<Task>? onClick = null)
    {
        var btn = new Button
        {
            Text = text,
            Height = 36,
            Width = 140,
            Margin = new Padding(0, 0, 8, 0),
        };
        ThemeHelper.StyleButton(btn, isPrimary);
        if (onClick != null)
            btn.Click += async (_, _) => await onClick();
        container.Controls.Add(btn);
    }

    private async Task UpdateStatusAsync(string targetStatus, string? approvedBy)
    {
        try
        {
            await _ipc.SendCommandAsync<object>("update_estimation_status", new
            {
                id = _estimationId,
                status = targetStatus,
                approved_by = approvedBy,
            });

            // Reload panel data to reflect the new status
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Failed to update status: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Export to external system
    // -------------------------------------------------------------------------

    private async Task ExportToExternalAsync()
    {
        try
        {
            var result = await _ipc.SendCommandAsync<ExportResult>("export_estimation", new
            {
                id = _estimationId,
            });

            var status = result.Status?.ToUpperInvariant();
            if (status == "SUCCESS")
            {
                MessageBox.Show("Estimation exported successfully.", "Export",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            else
            {
                var errors = result.Errors?.Count > 0 ? string.Join("\n", result.Errors) : "Unknown error";
                MessageBox.Show($"Export failed:\n{errors}", "Export Failed",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Export failed: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private sealed class ExportResult
    {
        [JsonPropertyName("status")] public string Status { get; set; } = "";
        [JsonPropertyName("system")] public string System { get; set; } = "";
        [JsonPropertyName("items_updated")] public int ItemsUpdated { get; set; }
        [JsonPropertyName("errors")] public List<string> Errors { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Report download
    // -------------------------------------------------------------------------

    private async Task DownloadReportAsync(string format, string dialogFilter)
    {
        try
        {
            var result = await _ipc.SendCommandAsync<ReportResult>("generate_report", new
            {
                id = _estimationId,
                format,
            });

            using var dlg = new SaveFileDialog
            {
                Title = "Save Report",
                Filter = $"{dialogFilter}|All Files|*.*",
                FileName = result.Filename,
            };

            if (dlg.ShowDialog() != DialogResult.OK) return;

            byte[] bytes = Convert.FromBase64String(result.ContentBase64);
            await File.WriteAllBytesAsync(dlg.FileName, bytes);

            MessageBox.Show($"Report saved to:\n{dlg.FileName}", "Report Saved",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Failed to generate report: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Grid event handlers
    // -------------------------------------------------------------------------

    private static void DgvTasks_CellFormatting(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.Value is not string text) return;

        // Column 1 = Type, Column 5 = New Feature Study
        if (e.ColumnIndex == 1)
        {
            e.CellStyle.ForeColor = GetTaskTypeColor(text);
            e.FormattingApplied = true;
        }
        else if (e.ColumnIndex == 5)
        {
            e.CellStyle.ForeColor = text == "Yes"
                ? ThemeHelper.FeasibilityAmber
                : ThemeHelper.TextSecondary;
            e.FormattingApplied = true;
        }
    }

    // -------------------------------------------------------------------------
    // Error display
    // -------------------------------------------------------------------------

    private void ShowLoadError(string message)
    {
        var lbl = new Label
        {
            Text = $"Failed to load estimation: {message}",
            ForeColor = ThemeHelper.FeasibilityRed,
            BackColor = Color.Transparent,
            Dock = DockStyle.Top,
            AutoSize = false,
            Height = 32,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(4, 0, 0, 0),
            Font = new Font("Segoe UI", 9.5f),
        };
        _scrollOuter.Controls.Add(lbl);
        lbl.BringToFront();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Color GetTaskTypeColor(string taskType) =>
        taskType?.ToUpperInvariant() switch
        {
            "SETUP"     => ThemeHelper.Accent,
            "EXECUTION" => ThemeHelper.FeasibilityGreen,
            "ANALYSIS"  => ThemeHelper.FeasibilityAmber,
            "REPORTING" => ThemeHelper.StatusFinal,
            "STUDY"     => ThemeHelper.StatusRevised,
            _           => ThemeHelper.TextSecondary,
        };
}
