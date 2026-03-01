using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class SettingsPanel
{
    private System.ComponentModel.IContainer? components = null;

    // -------------------------------------------------------------------------
    // Fields declared here for Designer awareness
    // -------------------------------------------------------------------------

    private Panel headerPanel = null!;
    private Label _headerLabel = null!;
    private Label _subtitleLabel = null!;
    private Panel toolbar = null!;
    private Button _btnRefresh = null!;
    private Button _btnSave = null!;
    private Panel backendPanel = null!;
    private Label backendLabel = null!;
    private TextBox txtBackendUrl = null!;
    private Button btnTestConnection = null!;
    private Button btnSaveUrl = null!;
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

        // UserControl properties
        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // --- Header panel ---
        headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 84,
            Padding = new Padding(0, 0, 0, 8),
        };

        _headerLabel = new Label
        {
            Text = "Settings",
            AutoSize = true,
            Location = new Point(0, 10),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);

        _subtitleLabel = new Label
        {
            Text = "Configure global defaults used in calculations and reports.",
            AutoSize = true,
            Location = new Point(0, 42),
        };
        ThemeHelper.StyleLabel(_subtitleLabel, isHeader: false);

        headerPanel.Controls.Add(_subtitleLabel);
        headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        toolbar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 52,
        };

        _btnRefresh = new Button
        {
            Text = "Refresh",
            Width = 90,
            Height = 38,
            Location = new Point(0, 7),
        };
        ThemeHelper.StyleButton(_btnRefresh, isPrimary: false);

        _btnSave = new Button
        {
            Text = "Save Changes",
            Width = 120,
            Height = 38,
            Location = new Point(96, 7),
        };
        ThemeHelper.StyleButton(_btnSave, isPrimary: true);

        toolbar.Controls.Add(_btnRefresh);
        toolbar.Controls.Add(_btnSave);

        // --- Backend URL section ---
        backendPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 56,
            Padding = new Padding(0, 4, 0, 8),
        };

        backendLabel = new Label
        {
            Text = "Backend URL:",
            AutoSize = true,
            Location = new Point(0, 10),
            ForeColor = ThemeHelper.Text,
            Font = new Font("Segoe UI", 9f),
        };

        txtBackendUrl = new TextBox
        {
            Location = new Point(100, 7),
            Width = 300,
            BackColor = ThemeHelper.Surface,
            ForeColor = ThemeHelper.Text,
            BorderStyle = BorderStyle.FixedSingle,
            Font = new Font("Segoe UI", 9f),
        };

        btnTestConnection = new Button
        {
            Text = "Test Connection",
            Width = 120,
            Height = 34,
            Location = new Point(410, 6),
        };
        ThemeHelper.StyleButton(btnTestConnection, isPrimary: false);

        btnSaveUrl = new Button
        {
            Text = "Save URL",
            Width = 90,
            Height = 34,
            Location = new Point(536, 6),
        };
        ThemeHelper.StyleButton(btnSaveUrl, isPrimary: true);

        backendPanel.Controls.Add(btnSaveUrl);
        backendPanel.Controls.Add(btnTestConnection);
        backendPanel.Controls.Add(txtBackendUrl);
        backendPanel.Controls.Add(backendLabel);

        // --- Grid ---
        _grid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = false,
            MultiSelect = false,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_grid);

        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Key",
            HeaderText = "Setting Key",
            ReadOnly = true,
            FillWeight = 25,
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Description",
            HeaderText = "Description",
            ReadOnly = true,
            FillWeight = 45,
        });
        _grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "Value",
            HeaderText = "Value",
            ReadOnly = false,
            FillWeight = 30,
        });

        _grid.Columns["Value"].DefaultCellStyle.BackColor = ThemeHelper.Surface;
        _grid.Columns["Value"].DefaultCellStyle.ForeColor = ThemeHelper.Text;

        // Layout — add in bottom-to-top order for DockStyle stacking
        Controls.Add(_grid);
        Controls.Add(toolbar);
        Controls.Add(backendPanel);
        Controls.Add(headerPanel);

        ResumeLayout(false);
    }
}
