using EstimationTool.Services;

namespace EstimationTool.Forms.Panels.WizardSteps;

partial class Step4DutProfile
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Designer-managed controls
    // -------------------------------------------------------------------------

    private TableLayoutPanel _outerLayout     = null!;
    private Label             _lblHeader      = null!;

    // Selection row
    private TableLayoutPanel  _selectionPanel = null!;
    private Panel             _dutPanel       = null!;
    private Label             _lblDuts        = null!;
    private CheckedListBox    _clbDuts        = null!;
    private Panel             _profilePanel   = null!;
    private Label             _lblProfiles    = null!;
    private CheckedListBox    _clbProfiles    = null!;

    // Matrix row
    private Panel             _matrixContainer = null!;
    private Label             _lblMatrix       = null!;
    private DataGridView      _dgvMatrix       = null!;

    // Bottom row
    private Panel             _bottomPanel     = null!;
    private Label             _lblSummary      = null!;
    private Label             _lblLoading      = null!;

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

        // ---- _outerLayout ----
        _outerLayout = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            RowCount    = 4,
            ColumnCount = 1,
            BackColor   = ThemeHelper.Background,
        };
        _outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // header
        _outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 200));  // selections
        _outerLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // matrix
        _outerLayout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));   // summary/loading
        _outerLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // ---- _lblHeader ----
        _lblHeader = new Label
        {
            Text      = "Step 4: DUT x Profile Matrix",
            Font      = new Font("Segoe UI", 14f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        _outerLayout.Controls.Add(_lblHeader, 0, 0);

        // ---- _selectionPanel ----
        _selectionPanel = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            ColumnCount = 2,
            RowCount    = 1,
            BackColor   = ThemeHelper.Background,
        };
        _selectionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        _selectionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        _selectionPanel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        // ---- _dutPanel + _lblDuts + _clbDuts ----
        _lblDuts = new Label
        {
            Text      = "DUT Types (select all that apply) *",
            Font      = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Top,
            Height    = 22,
        };

        _clbDuts = new CheckedListBox
        {
            Dock        = DockStyle.Fill,
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            CheckOnClick = true,
            Font        = new Font("Segoe UI", 9f),
        };

        _dutPanel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding   = new Padding(0, 0, 8, 0),
        };
        _dutPanel.Controls.Add(_clbDuts);
        _dutPanel.Controls.Add(_lblDuts);
        _selectionPanel.Controls.Add(_dutPanel, 0, 0);

        // ---- _profilePanel + _lblProfiles + _clbProfiles ----
        _lblProfiles = new Label
        {
            Text      = "Test Profiles (select all that apply) *",
            Font      = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Top,
            Height    = 22,
        };

        _clbProfiles = new CheckedListBox
        {
            Dock        = DockStyle.Fill,
            BackColor   = ThemeHelper.Surface,
            ForeColor   = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            CheckOnClick = true,
            Font        = new Font("Segoe UI", 9f),
        };

        _profilePanel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
            Padding   = new Padding(8, 0, 0, 0),
        };
        _profilePanel.Controls.Add(_clbProfiles);
        _profilePanel.Controls.Add(_lblProfiles);
        _selectionPanel.Controls.Add(_profilePanel, 1, 0);

        _outerLayout.Controls.Add(_selectionPanel, 0, 1);

        // ---- _matrixContainer + _lblMatrix + _dgvMatrix ----
        _lblMatrix = new Label
        {
            Text      = "Test Matrix — uncheck combinations you do NOT need to test:",
            Font      = new Font("Segoe UI Semibold", 9f, FontStyle.Bold),
            ForeColor = ThemeHelper.Text,
            BackColor = Color.Transparent,
            Dock      = DockStyle.Top,
            Height    = 22,
        };

        _dgvMatrix = new DataGridView
        {
            Dock                 = DockStyle.Fill,
            AllowUserToAddRows    = false,
            AllowUserToDeleteRows = false,
            ReadOnly             = false,
            EditMode             = DataGridViewEditMode.EditOnKeystrokeOrF2,
            RowHeadersVisible    = true,
            RowHeadersWidth      = 140,
            AutoSizeColumnsMode  = DataGridViewAutoSizeColumnsMode.AllCells,
        };
        ThemeHelper.StyleDataGridView(_dgvMatrix);
        _dgvMatrix.ReadOnly = false; // re-apply after StyleDataGridView
        _dgvMatrix.RowHeadersDefaultCellStyle.BackColor = ThemeHelper.Sidebar;
        _dgvMatrix.RowHeadersDefaultCellStyle.ForeColor = ThemeHelper.TextSecondary;
        _dgvMatrix.RowHeadersDefaultCellStyle.Font      = new Font("Segoe UI", 8.5f);

        _matrixContainer = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Background,
        };
        _matrixContainer.Controls.Add(_dgvMatrix);
        _matrixContainer.Controls.Add(_lblMatrix);
        _outerLayout.Controls.Add(_matrixContainer, 0, 2);

        // ---- _bottomPanel + _lblSummary + _lblLoading ----
        _lblSummary = new Label
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.Accent,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        _lblLoading = new Label
        {
            Text      = "Loading DUT types and profiles...",
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Font      = new Font("Segoe UI", 8.5f),
            ForeColor = ThemeHelper.TextSecondary,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(8, 0, 0, 0),
        };

        _bottomPanel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = ThemeHelper.Sidebar,
        };
        _bottomPanel.Controls.Add(_lblSummary);
        _bottomPanel.Controls.Add(_lblLoading);
        _outerLayout.Controls.Add(_bottomPanel, 0, 3);

        Controls.Add(_outerLayout);

        ResumeLayout(false);
    }
}
