using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step2Features
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Designer-managed controls
    // -------------------------------------------------------------------------

    private TableLayoutPanel _layoutMain = null!;
    private Label _lblHeader             = null!;
    private Label _lblInfo               = null!;
    private DataGridView _dgvFeatures    = null!;
    private Label _lblSummary            = null!;
    private Label _lblLoading            = null!;

    // DataGridView columns
    private DataGridViewCheckBoxColumn _colSelect   = null!;
    private DataGridViewCheckBoxColumn _colNew      = null!;
    private DataGridViewTextBoxColumn  _colName     = null!;
    private DataGridViewTextBoxColumn  _colCategory = null!;
    private DataGridViewTextBoxColumn  _colWeight   = null!;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        components = new System.ComponentModel.Container();
        SuspendLayout();

        // ---- UserControl base properties ----
        Dock       = DockStyle.Fill;
        BackColor  = ThemeHelper.Background;
        AutoScroll = true;

        // ---- _layoutMain ----
        _layoutMain = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 5,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));   // info bar
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // grid
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));   // summary
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));   // loading
        _layoutMain.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- _lblHeader ----
        _lblHeader = new Label
        {
            Text      = "Step 2: Select Features",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _layoutMain.Controls.Add(_lblHeader, 0, 0);

        // ---- _lblInfo ----
        _lblInfo = new Label
        {
            Text      = "  Check features to include. Mark \"New\" for features that need study time (16h study + 24h test creation).",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = ThemeHelper.Sidebar,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };
        _layoutMain.Controls.Add(_lblInfo, 0, 1);

        // ---- _dgvFeatures columns ----
        _colSelect = new DataGridViewCheckBoxColumn
        {
            HeaderText   = "Select",
            Name         = "ColSelect",
            Width        = 56,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable    = DataGridViewTriState.False,
        };

        _colNew = new DataGridViewCheckBoxColumn
        {
            HeaderText  = "New Feature",
            Name        = "ColNew",
            Width       = 88,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable    = DataGridViewTriState.False,
            ToolTipText  = "Mark features that have no existing tests — adds study (16h) + test creation (24h) tasks",
        };

        _colName = new DataGridViewTextBoxColumn
        {
            HeaderText   = "Feature Name",
            Name         = "ColName",
            ReadOnly     = true,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 160,
        };

        _colCategory = new DataGridViewTextBoxColumn
        {
            HeaderText   = "Category",
            Name         = "ColCategory",
            ReadOnly     = true,
            Width        = 110,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };

        _colWeight = new DataGridViewTextBoxColumn
        {
            HeaderText        = "Complexity",
            Name              = "ColWeight",
            ReadOnly          = true,
            Width             = 90,
            AutoSizeMode      = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle  = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        };

        // ---- _dgvFeatures ----
        _dgvFeatures = new DataGridView
        {
            Dock                 = DockStyle.Fill,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            ReadOnly             = false,
            MultiSelect          = false,
            EditMode             = DataGridViewEditMode.EditOnKeystrokeOrF2,
        };
        ThemeHelper.StyleDataGridView(_dgvFeatures);
        _dgvFeatures.ReadOnly = false; // re-apply after StyleDataGridView
        _dgvFeatures.Columns.AddRange(_colSelect, _colNew, _colName, _colCategory, _colWeight);
        _layoutMain.Controls.Add(_dgvFeatures, 0, 2);

        // ---- _lblSummary ----
        _lblSummary = new Label
        {
            Text      = "",
            Font      = new Font("Segoe UI", 8.5f, FontStyle.Bold),
            ForeColor = ThemeHelper.Accent,
            BackColor = ThemeHelper.Sidebar,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };
        _layoutMain.Controls.Add(_lblSummary, 0, 3);

        // ---- _lblLoading ----
        _lblLoading = new Label
        {
            Text      = "Loading features...",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = ThemeHelper.Background,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };
        _layoutMain.Controls.Add(_lblLoading, 0, 4);

        Controls.Add(_layoutMain);

        ResumeLayout(false);
    }
}
