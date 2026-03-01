using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class HistoryPanel
{
    private System.ComponentModel.IContainer? components = null;

    private Panel _headerPanel = null!;
    private Label _headerLabel = null!;
    private Label _subtitleLabel = null!;
    private Panel _toolbar = null!;
    private Button _btnAdd = null!;
    private DataGridView _grid = null!;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        SuspendLayout();

        // --- Header panel ---
        _headerPanel = new Panel
        {
            Dock   = DockStyle.Top,
            Height = 84,
        };

        _headerLabel = new Label
        {
            Text     = "Historical Projects",
            AutoSize = true,
            Location = new Point(0, 10),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);

        _subtitleLabel = new Label
        {
            Text     = "Reference projects used for calibrating estimation accuracy.",
            AutoSize = true,
            Location = new Point(0, 42),
        };
        ThemeHelper.StyleLabel(_subtitleLabel, isHeader: false);

        _headerPanel.Controls.Add(_subtitleLabel);
        _headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        _toolbar = new Panel
        {
            Dock   = DockStyle.Top,
            Height = 52,
        };

        _btnAdd = new Button
        {
            Text     = "Add Historical Project",
            Width    = 170,
            Height   = 38,
            Location = new Point(0, 7),
        };
        ThemeHelper.StyleButton(_btnAdd, isPrimary: true);
        _toolbar.Controls.Add(_btnAdd);

        // --- Grid ---
        _grid = new DataGridView
        {
            Dock                  = DockStyle.Fill,
            ReadOnly              = true,
            MultiSelect           = false,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_grid);

        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Id",             HeaderText = "ID",               FillWeight = 6  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProjectName",    HeaderText = "Project Name",     FillWeight = 24 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProjectType",    HeaderText = "Type",             FillWeight = 11 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "EstimatedHours", HeaderText = "Estimated Hours",  FillWeight = 13 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ActualHours",    HeaderText = "Actual Hours",     FillWeight = 11 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "DutCount",       HeaderText = "DUT Count",        FillWeight = 9  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ProfileCount",   HeaderText = "Profile Count",    FillWeight = 10 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "PrCount",        HeaderText = "PR Count",         FillWeight = 8  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "CompletionDate", HeaderText = "Completion Date",  FillWeight = 14 });

        // --- Layout ---
        Controls.Add(_grid);
        Controls.Add(_toolbar);
        Controls.Add(_headerPanel);

        ResumeLayout(false);
    }
}
