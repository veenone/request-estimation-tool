using System.Text.Json.Serialization;
using EstimationTool.Services;
using EstimationTool.Models;

namespace EstimationTool.Forms.Panels;

/// <summary>
/// Panel for managing the Device Under Test (DUT) registry.
/// Supports creating, editing, and deleting DUT types via the Python IPC backend.
/// </summary>
public class DutRegistryPanel : UserControl
{
    // -------------------------------------------------------------------------
    // IPC response wrapper
    // -------------------------------------------------------------------------

    private class DutTypesResponse
    {
        [JsonPropertyName("dut_types")]
        public List<DutType> DutTypes { get; set; } = new();
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly BackendApiService _ipc;

    private readonly DataGridView _grid;
    private readonly Button _btnAdd;
    private readonly Button _btnEdit;
    private readonly Button _btnDelete;
    private readonly Label _headerLabel;

    private List<DutType> _dutTypes = new();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public DutRegistryPanel(BackendApiService ipc)
    {
        _ipc = ipc;

        Dock = DockStyle.Fill;
        Padding = new Padding(0);

        // --- Header ---
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 48,
        };

        _headerLabel = new Label
        {
            Text = "DUT Registry",
            AutoSize = true,
            Location = new Point(0, 8),
        };
        ThemeHelper.StyleLabel(_headerLabel, isHeader: true);
        headerPanel.Controls.Add(_headerLabel);

        // --- Toolbar ---
        var toolbar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 40,
        };

        _btnAdd    = new Button { Text = "Add DUT",  Width = 90,  Height = 32, Location = new Point(0,   4) };
        _btnEdit   = new Button { Text = "Edit",     Width = 80,  Height = 32, Location = new Point(96,  4) };
        _btnDelete = new Button { Text = "Delete",   Width = 80,  Height = 32, Location = new Point(182, 4) };

        ThemeHelper.StyleButton(_btnAdd,    isPrimary: true);
        ThemeHelper.StyleButton(_btnEdit,   isPrimary: false);
        ThemeHelper.StyleButton(_btnDelete, isPrimary: false);

        toolbar.Controls.Add(_btnAdd);
        toolbar.Controls.Add(_btnEdit);
        toolbar.Controls.Add(_btnDelete);

        // --- Grid ---
        _grid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            MultiSelect = false,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
        };
        ThemeHelper.StyleDataGridView(_grid);

        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Id",                    HeaderText = "ID",                    FillWeight = 10 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Name",                  HeaderText = "Name",                  FillWeight = 35 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "Category",              HeaderText = "Category",              FillWeight = 35 });
        _grid.Columns.Add(new DataGridViewTextBoxColumn { Name = "ComplexityMultiplier",  HeaderText = "Complexity Multiplier", FillWeight = 20 });

        // -------------------------------------------------------------------------
        // Layout
        // -------------------------------------------------------------------------
        Controls.Add(_grid);
        Controls.Add(toolbar);
        Controls.Add(headerPanel);

        // -------------------------------------------------------------------------
        // Events
        // -------------------------------------------------------------------------
        _btnAdd.Click    += BtnAdd_Click;
        _btnEdit.Click   += BtnEdit_Click;
        _btnDelete.Click += BtnDelete_Click;
        _grid.CellDoubleClick += (s, e) => { if (e.RowIndex >= 0) OpenEditDialog(GetSelectedDut()); };

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
            var response = await _ipc.SendCommandAsync<DutTypesResponse>("get_dut_types");
            _dutTypes = response.DutTypes;

            _grid.Rows.Clear();
            foreach (var d in _dutTypes)
            {
                _grid.Rows.Add(
                    d.Id,
                    d.Name,
                    d.Category ?? "",
                    d.ComplexityMultiplier.ToString("F2"));
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to load DUT types:\n{ex.Message}",
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
        using var dialog = new DutDialog("Add DUT Type");
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        try
        {
            await _ipc.SendCommandAsync<object>("create_dut_type", new
            {
                name                  = dialog.DutName,
                category              = dialog.Category,
                complexity_multiplier = dialog.ComplexityMultiplier,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to create DUT type:\n{ex.Message}",
                "Create Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private void BtnEdit_Click(object? sender, EventArgs e)
    {
        var dut = GetSelectedDut();
        if (dut is null)
        {
            MessageBox.Show("Please select a DUT to edit.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        OpenEditDialog(dut);
    }

    private void OpenEditDialog(DutType? dut)
    {
        if (dut is null) return;

        using var dialog = new DutDialog("Edit DUT Type", dut);
        if (dialog.ShowDialog(this) != DialogResult.OK) return;

        _ = SaveEditAsync(dut.Id, dialog);
    }

    private async Task SaveEditAsync(int id, DutDialog dialog)
    {
        try
        {
            await _ipc.SendCommandAsync<object>("update_dut_type", new
            {
                id,
                name                  = dialog.DutName,
                category              = dialog.Category,
                complexity_multiplier = dialog.ComplexityMultiplier,
            });

            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to update DUT type:\n{ex.Message}",
                "Update Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private async void BtnDelete_Click(object? sender, EventArgs e)
    {
        var dut = GetSelectedDut();
        if (dut is null)
        {
            MessageBox.Show("Please select a DUT to delete.", "No Selection",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var confirm = MessageBox.Show(
            $"Delete DUT type \"{dut.Name}\"? This cannot be undone.",
            "Confirm Delete",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning);

        if (confirm != DialogResult.Yes) return;

        try
        {
            await _ipc.SendCommandAsync<object>("delete_dut_type", new { id = dut.Id });
            await LoadDataAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Failed to delete DUT type:\n{ex.Message}",
                "Delete Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private DutType? GetSelectedDut()
    {
        if (_grid.CurrentRow is null) return null;
        var id = _grid.CurrentRow.Cells["Id"].Value as int?
                 ?? (int.TryParse(_grid.CurrentRow.Cells["Id"].Value?.ToString(), out var parsed) ? parsed : -1);
        return _dutTypes.FirstOrDefault(d => d.Id == id);
    }
}

// =============================================================================
// DUT Add/Edit dialog
// =============================================================================

sealed class DutDialog : Form
{
    // Outputs
    public string DutName             => _txtName.Text.Trim();
    public string Category            => _txtCategory.Text.Trim();
    public double ComplexityMultiplier => (double)_nudMultiplier.Value;

    private readonly TextBox       _txtName;
    private readonly TextBox       _txtCategory;
    private readonly NumericUpDown _nudMultiplier;

    public DutDialog(string title, DutType? existing = null)
    {
        Text            = title;
        Size            = new Size(400, 260);
        MinimumSize     = new Size(360, 240);
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
            RowCount    = 5,
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

        // Complexity multiplier
        layout.Controls.Add(MakeLabel("Complexity Multiplier"), 0, 2);
        _nudMultiplier = new NumericUpDown
        {
            Dock          = DockStyle.Fill,
            Minimum       = 0.1m,
            Maximum       = 5.0m,
            DecimalPlaces = 2,
            Increment     = 0.1m,
            Value         = 1.0m,
        };
        ThemeHelper.ApplyTheme(_nudMultiplier);
        layout.Controls.Add(_nudMultiplier, 1, 2);

        // Buttons
        var btnPanel = new Panel { Dock = DockStyle.Fill };
        layout.Controls.Add(new Label(), 0, 3);
        layout.Controls.Add(btnPanel, 1, 3);

        var btnOk = new Button { Text = "Save", Width = 80, Height = 32, Location = new Point(0, 4) };
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

        var btnCancel = new Button { Text = "Cancel", Width = 80, Height = 32, Location = new Point(88, 4) };
        ThemeHelper.StyleButton(btnCancel, isPrimary: false);
        btnCancel.Click += (s, e) => DialogResult = DialogResult.Cancel;

        btnPanel.Controls.Add(btnOk);
        btnPanel.Controls.Add(btnCancel);

        Controls.Add(layout);

        // Pre-populate for edit mode
        if (existing is not null)
        {
            _txtName.Text        = existing.Name;
            _txtCategory.Text    = existing.Category ?? "";
            _nudMultiplier.Value = (decimal)Math.Clamp(existing.ComplexityMultiplier, 0.1, 5.0);
        }

        AcceptButton = btnOk;
        CancelButton = btnCancel;
    }

    private static Label MakeLabel(string text)
    {
        var lbl = new Label { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft };
        ThemeHelper.StyleLabel(lbl);
        return lbl;
    }
}
