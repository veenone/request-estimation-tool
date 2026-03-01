using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step3References
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Designer-managed controls
    // -------------------------------------------------------------------------

    private TableLayoutPanel _layoutMain   = null!;
    private Label             _lblHeader   = null!;
    private Panel             _infoPanel   = null!;
    private Label             _lblInfo     = null!;
    private DataGridView      _dgvProjects = null!;
    private Panel             _pnlAccuracy = null!;
    private Label             _lblAccuracy = null!;
    private Label             _lblLoading  = null!;

    // DataGridView columns
    private DataGridViewCheckBoxColumn _colCheck    = null!;
    private DataGridViewTextBoxColumn  _colName     = null!;
    private DataGridViewTextBoxColumn  _colType     = null!;
    private DataGridViewTextBoxColumn  _colEstimate = null!;
    private DataGridViewTextBoxColumn  _colActual   = null!;
    private DataGridViewTextBoxColumn  _colRatio    = null!;
    private DataGridViewTextBoxColumn  _colDate     = null!;

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
        Dock      = DockStyle.Fill;
        BackColor = ThemeHelper.Background;

        // ---- _layoutMain ----
        _layoutMain = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 5,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));   // info
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // grid
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));   // accuracy panel
        _layoutMain.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));   // loading
        _layoutMain.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- _lblHeader ----
        _lblHeader = new Label
        {
            Text      = "Step 3: Reference Projects",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _layoutMain.Controls.Add(_lblHeader, 0, 0);

        // ---- _infoPanel + _lblInfo ----
        _lblInfo = new Label
        {
            Text      = "Select historical projects to use as a calibration baseline (optional — you may skip by leaving all unchecked).\r\n" +
                        "An accuracy ratio > 1.0 means the team typically underestimates.",
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
        };

        _infoPanel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding   = new Padding(12, 8, 12, 8),
        };
        _infoPanel.Controls.Add(_lblInfo);
        _layoutMain.Controls.Add(_infoPanel, 0, 1);

        // ---- _dgvProjects columns ----
        _colCheck = new DataGridViewCheckBoxColumn
        {
            HeaderText   = "Select",
            Name         = "ColSelect",
            Width        = 56,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            Resizable    = DataGridViewTriState.False,
        };

        _colName = new DataGridViewTextBoxColumn
        {
            HeaderText   = "Project Name",
            Name         = "ColName",
            ReadOnly     = true,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            MinimumWidth = 160,
        };

        _colType = new DataGridViewTextBoxColumn
        {
            HeaderText   = "Type",
            Name         = "ColType",
            ReadOnly     = true,
            Width        = 90,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };

        _colEstimate = new DataGridViewTextBoxColumn
        {
            HeaderText       = "Estimated (h)",
            Name             = "ColEstimate",
            ReadOnly         = true,
            Width            = 100,
            AutoSizeMode     = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        };

        _colActual = new DataGridViewTextBoxColumn
        {
            HeaderText       = "Actual (h)",
            Name             = "ColActual",
            ReadOnly         = true,
            Width            = 90,
            AutoSizeMode     = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleRight },
        };

        _colRatio = new DataGridViewTextBoxColumn
        {
            HeaderText       = "Accuracy Ratio",
            Name             = "ColRatio",
            ReadOnly         = true,
            Width            = 100,
            AutoSizeMode     = DataGridViewAutoSizeColumnMode.None,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter },
        };

        _colDate = new DataGridViewTextBoxColumn
        {
            HeaderText   = "Completed",
            Name         = "ColDate",
            ReadOnly     = true,
            Width        = 96,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
        };

        // ---- _dgvProjects ----
        _dgvProjects = new DataGridView
        {
            Dock                 = DockStyle.Fill,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            ReadOnly             = false,
            EditMode             = DataGridViewEditMode.EditOnKeystrokeOrF2,
        };
        ThemeHelper.StyleDataGridView(_dgvProjects);
        _dgvProjects.ReadOnly = false; // re-apply after StyleDataGridView
        _dgvProjects.Columns.AddRange(_colCheck, _colName, _colType, _colEstimate, _colActual, _colRatio, _colDate);
        _layoutMain.Controls.Add(_dgvProjects, 0, 2);

        // ---- _pnlAccuracy + _lblAccuracy ----
        _lblAccuracy = new Label
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 9f),
            ForeColor = ThemeHelper.Text,
            TextAlign = ContentAlignment.MiddleLeft,
        };

        _pnlAccuracy = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
            Padding   = new Padding(12, 8, 12, 8),
            Visible   = false,
        };
        _pnlAccuracy.Controls.Add(_lblAccuracy);
        _layoutMain.Controls.Add(_pnlAccuracy, 0, 3);

        // ---- _lblLoading ----
        _lblLoading = new Label
        {
            Text      = "Loading historical projects...",
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
