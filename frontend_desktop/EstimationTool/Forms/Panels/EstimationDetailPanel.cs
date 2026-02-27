using EstimationTool.Models;
using EstimationTool.Services;
using System.Text.Json.Serialization;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Displays the full detail view for a single estimation: header info, effort
/// summary cards, status workflow controls, task breakdown grid, and report
/// download buttons. All UI is built programmatically — no designer file.
/// </summary>
public sealed class EstimationDetailPanel : UserControl
{
    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;
    private readonly MainForm _mainForm;
    private readonly int _estimationId;

    // Status workflow area — rebuilt whenever the estimation reloads
    private Panel _workflowPanel = null!;

    // Effort summary cards — value labels updated after load
    private Label _lblTesterHours = null!;
    private Label _lblLeaderHours = null!;
    private Label _lblGrandHours = null!;
    private Label _lblGrandDays = null!;
    private Label _lblFeasibility = null!;

    // Info grid value labels
    private Label _lblProjectType = null!;
    private Label _lblDutCount = null!;
    private Label _lblProfileCount = null!;
    private Label _lblCombinations = null!;
    private Label _lblPrFixCount = null!;
    private Label _lblDelivery = null!;
    private Label _lblCreatedBy = null!;
    private Label _lblCreatedAt = null!;

    // Status badge in header
    private Label _lblStatusBadge = null!;

    // Task breakdown grid
    private DataGridView _dgvTasks = null!;

    // Outer scrollable container — reassigned on reload
    private Panel _scrollOuter = null!;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public EstimationDetailPanel(BackendApiService ipc, MainForm mainForm, int estimationId)
    {
        _ipc = ipc;
        _mainForm = mainForm;
        _estimationId = estimationId;

        BackColor = ThemeHelper.Background;
        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        BuildLayout();

        HandleCreated += async (_, _) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Layout construction
    // -------------------------------------------------------------------------

    private void BuildLayout()
    {
        // Outer autoscroll panel fills the UserControl
        _scrollOuter = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(4),
        };
        Controls.Add(_scrollOuter);

        // Inner fixed-width stack that holds all sections
        var stack = new TableLayoutPanel
        {
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Dock = DockStyle.Top,
            BackColor = ThemeHelper.Background,
            ColumnCount = 1,
            RowCount = 8,
            Padding = new Padding(0),
        };
        stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));   // Row 0 — page header
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 1 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 120));  // Row 2 — info grid
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 3 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 100));  // Row 4 — effort cards
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 5 — spacer
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 100));  // Row 6 — workflow panel (placeholder)
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 8));    // Row 7 — spacer

        stack.Controls.Add(BuildHeader(), 0, 0);
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 1);
        stack.Controls.Add(BuildInfoGrid(), 0, 2);
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 3);
        stack.Controls.Add(BuildEffortCardsRow(), 0, 4);
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 5);

        // Workflow placeholder — replaced with real content after data loads
        _workflowPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Height = 90,
        };
        stack.Controls.Add(_workflowPanel, 0, 6);
        stack.Controls.Add(new Panel { Height = 8, BackColor = ThemeHelper.Background }, 0, 7);

        _scrollOuter.Controls.Add(stack);

        // Task breakdown section lives below the stack (not in TableLayoutPanel so
        // the grid can stretch to remaining vertical space naturally)
        var tasksSection = BuildTasksSection();
        tasksSection.Dock = DockStyle.Top;
        tasksSection.Height = 320;
        _scrollOuter.Controls.Add(tasksSection);

        // Space between tasks and report buttons
        _scrollOuter.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 8, BackColor = ThemeHelper.Background });

        // Report download buttons
        var reportsSection = BuildReportButtons();
        reportsSection.Dock = DockStyle.Top;
        _scrollOuter.Controls.Add(reportsSection);

        // Space at bottom
        _scrollOuter.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 16, BackColor = ThemeHelper.Background });

        // Reverse control order: WinForms DockStyle.Top stacks bottom-up
        // We need the stack at the actual top. Reverse by adding a back button
        // as the very first top-docked item so it appears at the bottom of the
        // scrollable area above the footer padding.
        var backBtn = new Button
        {
            Text = "Back to Dashboard",
            Dock = DockStyle.Bottom,
            Height = 32,
            Width = 160,
        };
        ThemeHelper.StyleButton(backBtn, isPrimary: false);
        backBtn.Click += (_, _) => _mainForm.NavigateTo("Dashboard");

        var backPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 44,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 6, 0, 6),
        };
        backPanel.Controls.Add(backBtn);
        Controls.Add(backPanel);
    }

    private Panel BuildHeader()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding = new Padding(0, 0, 0, 4),
        };

        // Status badge — updated after load
        _lblStatusBadge = new Label
        {
            Text = "—",
            AutoSize = false,
            Width = 90,
            Height = 24,
            Dock = DockStyle.Right,
            TextAlign = ContentAlignment.MiddleCenter,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            Margin = new Padding(0, 8, 0, 0),
        };

        // Main title label — updated after load
        var lblTitle = new Label
        {
            Name = "lblTitle",
            Text = "Loading...",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 16f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
            AutoEllipsis = true,
        };

        panel.Controls.Add(lblTitle);
        panel.Controls.Add(_lblStatusBadge);

        return panel;
    }

    private Panel BuildInfoGrid()
    {
        var outer = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(14, 10, 14, 10),
        };

        // 4-column label/value grid using TableLayoutPanel
        var tlp = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ColumnCount = 4,
            RowCount = 2,
            Padding = new Padding(0),
        };
        for (int i = 0; i < 4; i++)
            tlp.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25f));
        tlp.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));
        tlp.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));

        // Row 0
        tlp.Controls.Add(MakeLabelPair("Project Type", out _lblProjectType), 0, 0);
        tlp.Controls.Add(MakeLabelPair("DUT Count", out _lblDutCount), 1, 0);
        tlp.Controls.Add(MakeLabelPair("Profile Count", out _lblProfileCount), 2, 0);
        tlp.Controls.Add(MakeLabelPair("Combinations", out _lblCombinations), 3, 0);

        // Row 1
        tlp.Controls.Add(MakeLabelPair("PR Fix Count", out _lblPrFixCount), 0, 1);
        tlp.Controls.Add(MakeLabelPair("Expected Delivery", out _lblDelivery), 1, 1);
        tlp.Controls.Add(MakeLabelPair("Created By", out _lblCreatedBy), 2, 1);
        tlp.Controls.Add(MakeLabelPair("Created At", out _lblCreatedAt), 3, 1);

        outer.Controls.Add(tlp);

        outer.Paint += PaintSurfaceBorder;
        return outer;
    }

    private Panel BuildEffortCardsRow()
    {
        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0),
        };

        var cardTester = ThemeHelper.CreateMetricCard("Total Tester Hours", "—", ThemeHelper.Accent);
        var cardLeader = ThemeHelper.CreateMetricCard("Leader Hours", "—", ThemeHelper.StatusFinal);
        var cardGrandH = ThemeHelper.CreateMetricCard("Grand Total Hours", "—", ThemeHelper.FeasibilityAmber);
        var cardGrandD = ThemeHelper.CreateMetricCard("Grand Total Days", "—", ThemeHelper.StatusRevised);
        var cardFeas   = ThemeHelper.CreateMetricCard("Feasibility", "—", ThemeHelper.FeasibilityGreen);

        _lblTesterHours  = FindValueLabel(cardTester);
        _lblLeaderHours  = FindValueLabel(cardLeader);
        _lblGrandHours   = FindValueLabel(cardGrandH);
        _lblGrandDays    = FindValueLabel(cardGrandD);
        _lblFeasibility  = FindValueLabel(cardFeas);

        foreach (var card in new[] { cardTester, cardLeader, cardGrandH, cardGrandD, cardFeas })
        {
            card.Height = 86;
            card.Width = 170;
            card.Margin = new Padding(0, 0, 12, 0);
            flow.Controls.Add(card);
        }

        return flow;
    }

    private Panel BuildTasksSection()
    {
        var container = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(1),
        };

        var header = new Label
        {
            Text = "Task Breakdown",
            Dock = DockStyle.Top,
            Height = 34,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(8, 0, 0, 0),
        };
        container.Controls.Add(header);

        _dgvTasks = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            MultiSelect = false,
        };
        ThemeHelper.StyleDataGridView(_dgvTasks);

        _dgvTasks.Columns.AddRange(
            new DataGridViewTextBoxColumn { Name = "ColTaskName",    HeaderText = "Task Name",           FillWeight = 30 },
            new DataGridViewTextBoxColumn { Name = "ColTaskType",    HeaderText = "Type",                FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColBaseHours",   HeaderText = "Base Hours",          FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColCalcHours",   HeaderText = "Calculated Hours",    FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColLeadHours",   HeaderText = "Leader Hours",        FillWeight = 14 },
            new DataGridViewTextBoxColumn { Name = "ColNewStudy",    HeaderText = "New Feature Study",   FillWeight = 14 }
        );

        _dgvTasks.CellFormatting += DgvTasks_CellFormatting;

        container.Controls.Add(_dgvTasks);

        container.Paint += PaintSurfaceBorder;
        return container;
    }

    private Panel BuildReportButtons()
    {
        var outer = new Panel
        {
            BackColor = ThemeHelper.Surface,
            Padding = new Padding(14, 10, 14, 10),
            Height = 60,
        };

        var titleLabel = new Label
        {
            Text = "Download Report",
            Dock = DockStyle.Top,
            Height = 22,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI Semibold", 9.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };
        outer.Controls.Add(titleLabel);

        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0),
        };

        var btnExcel = MakeReportButton("Download Excel");
        var btnWord  = MakeReportButton("Download Word");
        var btnPdf   = MakeReportButton("Download PDF");

        btnExcel.Click += async (_, _) => await DownloadReportAsync("xlsx", "Excel Files|*.xlsx");
        btnWord.Click  += async (_, _) => await DownloadReportAsync("docx", "Word Documents|*.docx");
        btnPdf.Click   += async (_, _) => await DownloadReportAsync("pdf",  "PDF Files|*.pdf");

        flow.Controls.Add(btnExcel);
        flow.Controls.Add(btnWord);
        flow.Controls.Add(btnPdf);

        outer.Controls.Add(flow);
        outer.Paint += PaintSurfaceBorder;
        return outer;
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
        // Find the title label by name
        foreach (Control c in _scrollOuter.Controls)
        {
            if (c is TableLayoutPanel tlp)
            {
                var headerPanel = tlp.GetControlFromPosition(0, 0) as Panel;
                if (headerPanel != null)
                {
                    foreach (Control child in headerPanel.Controls)
                    {
                        if (child is Label lbl && lbl.Name == "lblTitle")
                        {
                            lbl.Text = $"{e.EstimationNumber ?? $"EST-{e.Id}"} — {e.ProjectName}";
                            break;
                        }
                    }
                }
                break;
            }
        }

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
            Height = 30,
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

    private static Panel MakeLabelPair(string caption, out Label valueLabel)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 2, 12, 2),
        };

        var captionLbl = new Label
        {
            Text = caption,
            Dock = DockStyle.Top,
            Height = 18,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font = new Font("Segoe UI", 8f),
            TextAlign = ContentAlignment.BottomLeft,
            AutoSize = false,
        };

        var valLbl = new Label
        {
            Text = "—",
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 10f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize = false,
            AutoEllipsis = true,
        };

        panel.Controls.Add(valLbl);
        panel.Controls.Add(captionLbl);

        valueLabel = valLbl;
        return panel;
    }

    private static Button MakeReportButton(string text)
    {
        var btn = new Button
        {
            Text = text,
            Height = 30,
            Width = 148,
            Margin = new Padding(0, 0, 10, 0),
        };
        ThemeHelper.StyleButton(btn, isPrimary: false);
        return btn;
    }

    /// <summary>
    /// CreateMetricCard places the Fill-docked value label first (Controls[0]).
    /// </summary>
    private static Label FindValueLabel(Panel card)
    {
        foreach (Control c in card.Controls)
        {
            if (c is Label lbl && lbl.Dock == DockStyle.Fill)
                return lbl;
        }
        return (Label)card.Controls[0];
    }

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

    private static void PaintSurfaceBorder(object? sender, PaintEventArgs e)
    {
        if (sender is not Panel p) return;
        using var pen = new Pen(ThemeHelper.Border, 1f);
        e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
    }
}
