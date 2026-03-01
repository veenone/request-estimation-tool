using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for managing the feature catalog. Supports creating, editing, and
/// deleting features via the Python IPC backend.
/// </summary>
public partial class FeatureCatalogPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class FeaturesResponse
    {
        [JsonPropertyName("features")]
        public List<Feature> Features { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private List<Feature> _features = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public FeatureCatalogPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock    = DockStyle.Fill;
        Padding = new Padding(0);

        InitializeComponent();

        _btnAdd.Click    += BtnAdd_Click;
        _btnEdit.Click   += BtnEdit_Click;
        _btnDelete.Click += BtnDelete_Click;
        _grid.CellDoubleClick += (s, e) => { if (e.RowIndex >= 0) OpenEditDialog(GetSelectedFeature()); };

        ThemeHelper.ApplyTheme(this);

        Load += async (s, e) => await LoadDataAsync();
    }

    // -------------------------------------------------------------------------
    // Data loading
    // -------------------------------------------------------------------------

    private async Task LoadDataAsync()
    {
        try
        {
            var response = await _ipc.SendCommandAsync<FeaturesResponse>("get_features");
            _features = response.Features;

            _grid.Rows.Clear();
            foreach (var f in _features)
            {
                _grid.Rows.Add(
                    f.Id,
                    f.Name,
                    f.Category ?? "",
                    f.ComplexityWeight.ToString("F2"),
                    f.HasExistingTests,
                    f.Description ?? "");
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load features:\n{ex.Message}",
                "Load Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Button handlers
    // -------------------------------------------------------------------------

    private async void BtnAdd_Click(object? sender, EventArgs e)
    {
        using var dialog = new FeatureDialog("Add Feature");
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_feature", new
            {
                name                = dialog.FeatureName,
                category            = dialog.Category,
                complexity_weight   = dialog.ComplexityWeight,
                has_existing_tests  = dialog.HasExistingTests,
                description         = dialog.Description,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create feature:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnEdit_Click(object? sender, EventArgs e)
    {
        var feature = GetSelectedFeature();
        if (feature is null)
        {
            MessageBox.Show("Please select a feature to edit.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        OpenEditDialog(feature);
        await Task.CompletedTask;
    }

    private void OpenEditDialog(Feature? feature)
    {
        if (feature is null) return;

        using var dialog = new FeatureDialog("Edit Feature", feature);
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        _ = SaveEditAsync(feature.Id, dialog);
    }

    private async Task SaveEditAsync(int id, FeatureDialog dialog)
    {
        try
        {
            await _ipc.SendCommandAsync<object>("update_feature", new
            {
                id,
                name                = dialog.FeatureName,
                category            = dialog.Category,
                complexity_weight   = dialog.ComplexityWeight,
                has_existing_tests  = dialog.HasExistingTests,
                description         = dialog.Description,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to update feature:\n{ex.Message}",
                "Update Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnDelete_Click(object? sender, EventArgs e)
    {
        var feature = GetSelectedFeature();
        if (feature is null)
        {
            MessageBox.Show("Please select a feature to delete.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var confirm = MessageBox.Show(
            $"Delete feature \"{feature.Name}\"? This cannot be undone.",
            "Confirm Delete",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning);

        if (confirm != DialogResult.Yes) return;

        try
        {
            await _ipc.SendCommandAsync<object>("delete_feature", new { id = feature.Id });
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to delete feature:\n{ex.Message}",
                "Delete Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private Feature? GetSelectedFeature()
    {
        if (_grid.CurrentRow is null) return null;
        var id = _grid.CurrentRow.Cells["Id"].Value as int?
                 ?? (int.TryParse(_grid.CurrentRow.Cells["Id"].Value?.ToString(), out var parsed) ? parsed : -1);
        return _features.FirstOrDefault(f => f.Id == id);
    }
}

// =============================================================================
// Feature Add/Edit dialog
// =============================================================================

sealed class FeatureDialog : Form
{
    // Outputs
    public string FeatureName      => _txtName.Text.Trim();
    public string Category         => _txtCategory.Text.Trim();
    public double ComplexityWeight => (double)_nudComplexity.Value;
    public bool   HasExistingTests => _chkHasTests.Checked;
    public string Description      => _txtDescription.Text.Trim();

    private readonly TextBox        _txtName;
    private readonly TextBox        _txtCategory;
    private readonly NumericUpDown  _nudComplexity;
    private readonly CheckBox       _chkHasTests;
    private readonly TextBox        _txtDescription;

    public FeatureDialog(string title, Feature? existing = null)
    {
        Text            = title;
        Size            = new Size(420, 360);
        MinimumSize     = new Size(380, 320);
        StartPosition   = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false;
        MinimizeBox     = false;
        BackColor       = ThemeHelper.Background;
        ForeColor       = ThemeHelper.Text;

        var layout = new TableLayoutPanel
        {
            Dock        = DockStyle.Fill,
            ColumnCount = 2,
            RowCount    = 7,
            Padding     = new Padding(16),
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 140));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        // Name
        layout.Controls.Add(MakeLabel("Name *"), 0, 0);
        _txtName = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtName);
        layout.Controls.Add(_txtName, 1, 0);

        // Category
        layout.Controls.Add(MakeLabel("Category"), 0, 1);
        _txtCategory = new TextBox { Dock = DockStyle.Fill };
        ThemeHelper.StyleTextBox(_txtCategory);
        layout.Controls.Add(_txtCategory, 1, 1);

        // Complexity weight
        layout.Controls.Add(MakeLabel("Complexity Weight"), 0, 2);
        _nudComplexity = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0.1m,
            Maximum       = 10.0m,
            DecimalPlaces = 2,
            Increment     = 0.1m,
            Value         = 1.0m,
        };
        ThemeHelper.ApplyTheme(_nudComplexity);
        layout.Controls.Add(_nudComplexity, 1, 2);

        // Has existing tests
        layout.Controls.Add(MakeLabel("Has Existing Tests"), 0, 3);
        _chkHasTests = new CheckBox { Dock = DockStyle.Fill, Text = "" };
        ThemeHelper.ApplyTheme(_chkHasTests);
        layout.Controls.Add(_chkHasTests, 1, 3);

        // Description
        layout.Controls.Add(MakeLabel("Description"), 0, 4);
        _txtDescription = new TextBox
        {
            Dock      = DockStyle.Fill,
            Multiline = true,
            Height    = 60,
        };
        ThemeHelper.StyleTextBox(_txtDescription);
        layout.Controls.Add(_txtDescription, 1, 4);
        layout.SetRowSpan(_txtDescription, 1);
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 70));

        // Buttons row
        var btnPanel = new Panel { Dock = DockStyle.Fill, Height = 40 };
        layout.Controls.Add(new Label(), 0, 5);
        layout.Controls.Add(btnPanel, 1, 5);

        var btnOk = new Button
        {
            Text     = "Save",
            Width    = 80,
            Height   = 32,
            Location = new Point(0, 4),
        };
        ThemeHelper.StyleButton(btnOk, isPrimary: true);
        btnOk.Click += (s, e) =>
        {
            if (string.IsNullOrWhiteSpace(_txtName.Text))
            {
                MessageBox.Show("Name is required.", "Validation", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            DialogResult = DialogResult.OK;
        };

        var btnCancel = new Button
        {
            Text     = "Cancel",
            Width    = 80,
            Height   = 32,
            Location = new Point(88, 4),
        };
        ThemeHelper.StyleButton(btnCancel, isPrimary: false);
        btnCancel.Click += (s, e) => DialogResult = DialogResult.Cancel;

        btnPanel.Controls.Add(btnOk);
        btnPanel.Controls.Add(btnCancel);

        Controls.Add(layout);

        // Pre-populate for edit mode
        if (existing is not null)
        {
            _txtName.Text           = existing.Name;
            _txtCategory.Text       = existing.Category ?? "";
            _nudComplexity.Value    = (decimal)Math.Clamp(existing.ComplexityWeight, 0.1, 10.0);
            _chkHasTests.Checked    = existing.HasExistingTests;
            _txtDescription.Text    = existing.Description ?? "";
        }

        AcceptButton = btnOk;
        CancelButton = btnCancel;
    }

    private static Label MakeLabel(string text)
    {
        var lbl = new Label
        {
            Text      = text,
            Dock      = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        ThemeHelper.StyleLabel(lbl);
        return lbl;
    }
}
