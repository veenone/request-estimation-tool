using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class FeatureCatalogPanel
{
    private System.ComponentModel.IContainer? components = null;

    private Panel _headerPanel = null!;
    private Label _headerLabel = null!;
    private Panel _toolbar = null!;
    private Button _btnAdd = null!;
    private Button _btnEdit = null!;
    private Button _btnDelete = null!;
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
            Height = 76,
        };

        _headerLabel = new Label
        {
            Text     = "Feature Catalog",
            AutoSize = true,
            Location = new Point(0, 14),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);
        _headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        _toolbar = new Panel
        {
            Dock   = DockStyle.Top,
            Height = 52,
        };

        _btnAdd    = new Button { Text = "Add Feature", Width = 110, Height = 38, Location = new Point(0,   7) };
        _btnEdit   = new Button { Text = "Edit",        Width = 80,  Height = 38, Location = new Point(116, 7) };
        _btnDelete = new Button { Text = "Delete",      Width = 80,  Height = 38, Location = new Point(202, 7) };

        ThemeHelper.StyleButton(_btnAdd,    isPrimary: true);
        ThemeHelper.StyleButton(_btnEdit,   isPrimary: false);
        ThemeHelper.StyleButton(_btnDelete, isPrimary: false);

        _toolbar.Controls.Add(_btnAdd);
        _toolbar.Controls.Add(_btnEdit);
        _toolbar.Controls.Add(_btnDelete);

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

        _grid.Columns.Add(new DataGridViewTextBoxColumn  { Name = "Id",               HeaderText = "ID",                FillWeight = 8  });
        _grid.Columns.Add(new DataGridViewTextBoxColumn  { Name = "Name",             HeaderText = "Name",              FillWeight = 30 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn  { Name = "Category",         HeaderText = "Category",          FillWeight = 20 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn  { Name = "ComplexityWeight", HeaderText = "Complexity Weight", FillWeight = 18 });
        _grid.Columns.Add(new DataGridViewCheckBoxColumn { Name = "HasTests",         HeaderText = "Has Tests",         FillWeight = 14 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn  { Name = "Description",      HeaderText = "Description",       FillWeight = 30 });

        // --- Layout ---
        Controls.Add(_grid);
        Controls.Add(_toolbar);
        Controls.Add(_headerPanel);

        ResumeLayout(false);
    }
}
