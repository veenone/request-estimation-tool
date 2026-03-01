namespace EstimationTool.Services;

/// <summary>
/// Theme enumeration for light and dark mode support.
/// </summary>
public enum AppTheme
{
    Dark,
    Light
}

/// <summary>
/// Provides theme-aware constants and helper methods for consistently styling
/// WinForms controls throughout the application. Supports both dark and light themes.
/// </summary>
public static class ThemeHelper
{
    // -------------------------------------------------------------------------
    // Theme state
    // -------------------------------------------------------------------------

    private static AppTheme _currentTheme = AppTheme.Dark;

    /// <summary>
    /// Gets or sets the current application theme.
    /// </summary>
    public static AppTheme CurrentTheme
    {
        get => _currentTheme;
        private set => _currentTheme = value;
    }

    /// <summary>
    /// Raised when the theme changes. Subscribers should re-apply theming.
    /// </summary>
    public static event EventHandler<AppTheme>? ThemeChanged;

    /// <summary>
    /// Switches to the specified theme and raises <see cref="ThemeChanged"/>.
    /// </summary>
    public static void SetTheme(AppTheme theme)
    {
        if (_currentTheme == theme) return;
        _currentTheme = theme;
        ThemeChanged?.Invoke(null, theme);
    }

    /// <summary>
    /// Toggles between Dark and Light themes.
    /// </summary>
    public static void ToggleTheme()
    {
        SetTheme(_currentTheme == AppTheme.Dark ? AppTheme.Light : AppTheme.Dark);
    }

    // -------------------------------------------------------------------------
    // Dark palette
    // -------------------------------------------------------------------------

    private static readonly Color DarkBackground   = ColorFromHex("#1E1E2E");
    private static readonly Color DarkSurface      = ColorFromHex("#2A2A3E");
    private static readonly Color DarkSidebar      = ColorFromHex("#181825");
    private static readonly Color DarkSidebarHover = ColorFromHex("#313244");
    private static readonly Color DarkAccent       = ColorFromHex("#2F5496");
    private static readonly Color DarkAccentHover  = ColorFromHex("#3A65B0");
    private static readonly Color DarkText         = ColorFromHex("#CDD6F4");
    private static readonly Color DarkTextSecondary = ColorFromHex("#A6ADC8");
    private static readonly Color DarkBorder       = ColorFromHex("#45475A");

    // -------------------------------------------------------------------------
    // Light palette
    // -------------------------------------------------------------------------

    private static readonly Color LightBackground   = ColorFromHex("#FFFFFF");
    private static readonly Color LightSurface      = ColorFromHex("#F5F5F5");
    private static readonly Color LightSidebar      = ColorFromHex("#E8E8E8");
    private static readonly Color LightSidebarHover = ColorFromHex("#D0D0D0");
    private static readonly Color LightAccent       = ColorFromHex("#2F5496");
    private static readonly Color LightAccentHover  = ColorFromHex("#3A65B0");
    private static readonly Color LightText         = ColorFromHex("#1E1E2E");
    private static readonly Color LightTextSecondary = ColorFromHex("#555555");
    private static readonly Color LightBorder       = ColorFromHex("#CCCCCC");

    // -------------------------------------------------------------------------
    // Theme-aware color properties
    // -------------------------------------------------------------------------

    public static Color Background     => _currentTheme == AppTheme.Dark ? DarkBackground   : LightBackground;
    public static Color Surface        => _currentTheme == AppTheme.Dark ? DarkSurface      : LightSurface;
    public static Color Sidebar        => _currentTheme == AppTheme.Dark ? DarkSidebar      : LightSidebar;
    public static Color SidebarHover   => _currentTheme == AppTheme.Dark ? DarkSidebarHover : LightSidebarHover;
    public static Color Accent         => _currentTheme == AppTheme.Dark ? DarkAccent       : LightAccent;
    public static Color AccentHover    => _currentTheme == AppTheme.Dark ? DarkAccentHover  : LightAccentHover;
    public static Color Text           => _currentTheme == AppTheme.Dark ? DarkText         : LightText;
    public static Color TextSecondary  => _currentTheme == AppTheme.Dark ? DarkTextSecondary : LightTextSecondary;
    public static Color Border         => _currentTheme == AppTheme.Dark ? DarkBorder       : LightBorder;

    // -------------------------------------------------------------------------
    // Semantic / status colors (same for both themes)
    // -------------------------------------------------------------------------

    // Feasibility
    public static readonly Color FeasibilityGreen = ColorFromHex("#28a745");
    public static readonly Color FeasibilityAmber = ColorFromHex("#ffc107");
    public static readonly Color FeasibilityRed   = ColorFromHex("#dc3545");

    // Estimation status
    public static readonly Color StatusDraft    = ColorFromHex("#6c757d");
    public static readonly Color StatusFinal    = ColorFromHex("#0d6efd");
    public static readonly Color StatusApproved = ColorFromHex("#198754");
    public static readonly Color StatusRevised  = ColorFromHex("#fd7e14");

    // -------------------------------------------------------------------------
    // Typography helpers
    // -------------------------------------------------------------------------

    private static readonly Font DefaultFont  = new("Segoe UI", 9.5f, FontStyle.Regular);
    private static readonly Font HeaderFont   = new("Segoe UI", 14f, FontStyle.Bold);
    private static readonly Font MetricFont   = new("Segoe UI", 18f, FontStyle.Bold);
    private static readonly Font SubtitleFont = new("Segoe UI", 9f, FontStyle.Regular);

    // -------------------------------------------------------------------------
    // ApplyTheme — recursive
    // -------------------------------------------------------------------------

    /// <summary>
    /// Recursively applies the current theme BackColor and ForeColor to a control
    /// and all of its children.
    /// </summary>
    public static void ApplyTheme(Control control)
    {
        ApplyThemeInternal(control, isTopLevel: true);
    }

    private static void ApplyThemeInternal(Control control, bool isTopLevel)
    {
        switch (control)
        {
            case Form form:
                form.BackColor = Background;
                form.ForeColor = Text;
                break;

            case TabPage tp:
                tp.BackColor = Background;
                tp.ForeColor = Text;
                break;

            case Panel panel:
                panel.BackColor = Surface;
                panel.ForeColor = Text;
                break;

            case Button btn:
                StyleButton(btn);
                break;

            case DataGridView dgv:
                StyleDataGridView(dgv);
                break;

            case TextBox txt:
                StyleTextBox(txt);
                break;

            case ComboBox cmb:
                StyleComboBox(cmb);
                break;

            case Label lbl:
                lbl.BackColor = Color.Transparent;
                lbl.ForeColor = Text;
                lbl.Font = DefaultFont;
                break;

            case ListBox lb:
                lb.BackColor = Surface;
                lb.ForeColor = Text;
                lb.BorderStyle = BorderStyle.FixedSingle;
                break;

            case CheckBox cb:
                cb.BackColor = Color.Transparent;
                cb.ForeColor = Text;
                break;

            case RadioButton rb:
                rb.BackColor = Color.Transparent;
                rb.ForeColor = Text;
                break;

            case NumericUpDown nud:
                nud.BackColor = Surface;
                nud.ForeColor = Text;
                nud.BorderStyle = BorderStyle.FixedSingle;
                break;

            case TabControl tc:
                tc.BackColor = Background;
                tc.ForeColor = Text;
                break;

            case GroupBox gb:
                gb.BackColor = Surface;
                gb.ForeColor = TextSecondary;
                break;

            case ToolStrip ts:
                ts.BackColor = Sidebar;
                ts.ForeColor = Text;
                ts.Renderer = new DarkToolStripRenderer();
                break;

            default:
                if (!isTopLevel)
                {
                    control.BackColor = Surface;
                    control.ForeColor = Text;
                }
                break;
        }

        foreach (Control child in control.Controls)
            ApplyThemeInternal(child, isTopLevel: false);
    }

    // -------------------------------------------------------------------------
    // StyleButton
    // -------------------------------------------------------------------------

    /// <summary>
    /// Applies flat-style button theming. Primary buttons use the Accent color;
    /// secondary buttons use the Surface color.
    /// </summary>
    public static void StyleButton(Button btn, bool isPrimary = false)
    {
        btn.FlatStyle = FlatStyle.Flat;
        btn.Font = DefaultFont;
        btn.Cursor = Cursors.Hand;
        btn.ForeColor = isPrimary ? Color.White : Text;

        if (isPrimary)
        {
            btn.BackColor = Accent;
            btn.FlatAppearance.BorderColor = Accent;
            btn.FlatAppearance.MouseOverBackColor = AccentHover;
            btn.FlatAppearance.MouseDownBackColor = ColorFromHex("#254880");
        }
        else
        {
            btn.BackColor = Surface;
            btn.FlatAppearance.BorderColor = Border;
            btn.FlatAppearance.MouseOverBackColor = SidebarHover;
            btn.FlatAppearance.MouseDownBackColor = Border;
        }

        btn.FlatAppearance.BorderSize = 1;
        btn.Padding = new Padding(8, 4, 8, 4);
    }

    // -------------------------------------------------------------------------
    // StyleSidebarButton
    // -------------------------------------------------------------------------

    /// <summary>
    /// Styles a button for use in a sidebar navigation panel.
    /// Active buttons are highlighted with the Accent color.
    /// </summary>
    public static void StyleSidebarButton(Button btn, bool isActive = false)
    {
        btn.FlatStyle = FlatStyle.Flat;
        btn.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
        btn.Cursor = Cursors.Hand;
        btn.ForeColor = isActive ? (_currentTheme == AppTheme.Dark ? DarkText : Color.White) : TextSecondary;
        btn.TextAlign = ContentAlignment.MiddleLeft;
        btn.Dock = DockStyle.Top;
        btn.Height = 44;
        btn.Padding = new Padding(16, 0, 8, 0);

        btn.BackColor = isActive ? Accent : Sidebar;
        btn.FlatAppearance.BorderSize = 0;
        btn.FlatAppearance.MouseOverBackColor = isActive ? AccentHover : SidebarHover;
        btn.FlatAppearance.MouseDownBackColor = isActive ? Accent : Border;
    }

    // -------------------------------------------------------------------------
    // StyleDataGridView
    // -------------------------------------------------------------------------

    /// <summary>
    /// Applies the current theme to a DataGridView with alternating row colors,
    /// hidden row headers, and auto-sized columns.
    /// </summary>
    public static void StyleDataGridView(DataGridView dgv)
    {
        dgv.BackgroundColor = Background;
        dgv.BorderStyle = BorderStyle.None;
        dgv.CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal;
        dgv.GridColor = Border;
        dgv.RowHeadersVisible = false;
        dgv.EnableHeadersVisualStyles = false;
        dgv.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
        dgv.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        dgv.AllowUserToResizeRows = false;

        // Default cell style
        dgv.DefaultCellStyle.BackColor = Surface;
        dgv.DefaultCellStyle.ForeColor = Text;
        dgv.DefaultCellStyle.SelectionBackColor = Accent;
        dgv.DefaultCellStyle.SelectionForeColor = _currentTheme == AppTheme.Dark ? Text : Color.White;
        dgv.DefaultCellStyle.Font = DefaultFont;
        dgv.DefaultCellStyle.Padding = new Padding(4, 2, 4, 2);

        // Alternating row style
        dgv.AlternatingRowsDefaultCellStyle.BackColor = Background;
        dgv.AlternatingRowsDefaultCellStyle.ForeColor = Text;
        dgv.AlternatingRowsDefaultCellStyle.SelectionBackColor = Accent;
        dgv.AlternatingRowsDefaultCellStyle.SelectionForeColor = _currentTheme == AppTheme.Dark ? Text : Color.White;

        // Column header style
        dgv.ColumnHeadersDefaultCellStyle.BackColor = Sidebar;
        dgv.ColumnHeadersDefaultCellStyle.ForeColor = TextSecondary;
        dgv.ColumnHeadersDefaultCellStyle.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
        dgv.ColumnHeadersDefaultCellStyle.SelectionBackColor = Sidebar;
        dgv.ColumnHeadersDefaultCellStyle.SelectionForeColor = TextSecondary;
        dgv.ColumnHeadersBorderStyle = DataGridViewHeaderBorderStyle.Single;
        dgv.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.DisableResizing;
        dgv.ColumnHeadersHeight = 40;

        // Explicit row height to prevent text truncation
        dgv.RowTemplate.Height = 36;
    }

    // -------------------------------------------------------------------------
    // StyleTextBox
    // -------------------------------------------------------------------------

    /// <summary>
    /// Applies consistent theme styling to a TextBox.
    /// </summary>
    public static void StyleTextBox(TextBox txt)
    {
        txt.BackColor = Surface;
        txt.ForeColor = Text;
        txt.BorderStyle = BorderStyle.FixedSingle;
        txt.Font = DefaultFont;
    }

    // -------------------------------------------------------------------------
    // StyleComboBox
    // -------------------------------------------------------------------------

    /// <summary>
    /// Applies consistent theme styling to a ComboBox.
    /// Note: WinForms ComboBox has limited owner-draw support; this sets
    /// the most impactful properties.
    /// </summary>
    public static void StyleComboBox(ComboBox cmb)
    {
        cmb.BackColor = Surface;
        cmb.ForeColor = Text;
        cmb.FlatStyle = FlatStyle.Flat;
        cmb.Font = DefaultFont;
    }

    // -------------------------------------------------------------------------
    // StylePanel
    // -------------------------------------------------------------------------

    /// <summary>
    /// Styles a Panel to appear as a card with a subtle border.
    /// </summary>
    public static void StylePanel(Panel panel)
    {
        panel.BackColor = Surface;
        panel.ForeColor = Text;
        panel.Padding = new Padding(12);

        // WinForms does not natively support border-radius, but we can paint one
        panel.Paint += PanelPaint_RoundedBorder;
    }

    private static void PanelPaint_RoundedBorder(object? sender, PaintEventArgs e)
    {
        if (sender is not Panel panel) return;

        using var pen = new Pen(Border, 1f);
        var rect = new Rectangle(0, 0, panel.Width - 1, panel.Height - 1);
        e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        DrawRoundedRectangle(e.Graphics, pen, rect, radius: 6);
    }

    // -------------------------------------------------------------------------
    // StyleLabel
    // -------------------------------------------------------------------------

    /// <summary>
    /// Styles a Label. Headers get larger bold font; regular labels use default font.
    /// </summary>
    public static void StyleLabel(Label lbl, bool isHeader = false)
    {
        lbl.BackColor = Color.Transparent;
        lbl.ForeColor = isHeader ? Text : TextSecondary;
        lbl.Font = isHeader ? HeaderFont : DefaultFont;
    }

    // -------------------------------------------------------------------------
    // Semantic color helpers
    // -------------------------------------------------------------------------

    /// <summary>
    /// Returns the appropriate color for a feasibility status string.
    /// Recognizes: FEASIBLE, AT_RISK, NOT_FEASIBLE (case-insensitive).
    /// </summary>
    public static Color GetFeasibilityColor(string status) =>
        status?.ToUpperInvariant() switch
        {
            "FEASIBLE"     => FeasibilityGreen,
            "AT_RISK"      => FeasibilityAmber,
            "NOT_FEASIBLE" => FeasibilityRed,
            _              => TextSecondary
        };

    /// <summary>
    /// Returns the appropriate color for an estimation status string.
    /// Recognizes: DRAFT, FINAL, APPROVED, REVISED (case-insensitive).
    /// </summary>
    public static Color GetStatusColor(string status) =>
        status?.ToUpperInvariant() switch
        {
            "DRAFT"    => StatusDraft,
            "FINAL"    => StatusFinal,
            "APPROVED" => StatusApproved,
            "REVISED"  => StatusRevised,
            _          => TextSecondary
        };

    // -------------------------------------------------------------------------
    // CreateMetricCard
    // -------------------------------------------------------------------------

    /// <summary>
    /// Creates a styled Panel containing a title Label and a value Label,
    /// suitable for use in a dashboard metrics row.
    /// </summary>
    /// <param name="title">The card's subtitle/description text.</param>
    /// <param name="value">The primary metric value to display.</param>
    /// <param name="accentColor">
    /// Optional accent color applied to the left border of the card.
    /// Defaults to <see cref="Accent"/> if not provided.
    /// </param>
    public static Panel CreateMetricCard(string title, string value, Color? accentColor = null)
    {
        var resolvedAccent = accentColor ?? Accent;

        var card = new Panel
        {
            BackColor = Surface,
            Padding = new Padding(14, 10, 14, 10),
            MinimumSize = new Size(160, 90)
        };

        var titleLabel = new Label
        {
            Text = title,
            Dock = DockStyle.Top,
            BackColor = Color.Transparent,
            ForeColor = TextSecondary,
            Font = SubtitleFont,
            AutoSize = false,
            Height = 24,
            TextAlign = ContentAlignment.BottomLeft
        };

        var valueLabel = new Label
        {
            Text = value,
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = Text,
            Font = MetricFont,
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize = false
        };

        // Add in reverse order due to DockStyle.Top stacking
        card.Controls.Add(valueLabel);
        card.Controls.Add(titleLabel);

        // Paint accent bar on left edge + subtle border
        card.Paint += (sender, e) =>
        {
            if (sender is not Panel p) return;

            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

            // Rounded outer border
            using var borderPen = new Pen(Border, 1f);
            DrawRoundedRectangle(e.Graphics, borderPen,
                new Rectangle(0, 0, p.Width - 1, p.Height - 1), radius: 6);

            // Accent bar on the left
            using var accentBrush = new SolidBrush(resolvedAccent);
            e.Graphics.FillRectangle(accentBrush,
                new Rectangle(0, 4, 3, p.Height - 8));
        };

        return card;
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private static Color ColorFromHex(string hex)
    {
        hex = hex.TrimStart('#');
        return Color.FromArgb(
            Convert.ToInt32(hex[0..2], 16),
            Convert.ToInt32(hex[2..4], 16),
            Convert.ToInt32(hex[4..6], 16));
    }

    private static void DrawRoundedRectangle(
        Graphics g, Pen pen, Rectangle bounds, int radius)
    {
        int d = radius * 2;
        using var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        g.DrawPath(pen, path);
    }

    // -------------------------------------------------------------------------
    // Private renderer
    // -------------------------------------------------------------------------

    /// <summary>
    /// Minimal ToolStrip renderer that suppresses default borders and light backgrounds.
    /// </summary>
    private sealed class DarkToolStripRenderer : ToolStripProfessionalRenderer
    {
        public DarkToolStripRenderer()
            : base(new DarkColorTable()) { }

        protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e) { }
    }

    private sealed class DarkColorTable : ProfessionalColorTable
    {
        public override Color ToolStripGradientBegin => Sidebar;
        public override Color ToolStripGradientMiddle => Sidebar;
        public override Color ToolStripGradientEnd => Sidebar;
        public override Color MenuStripGradientBegin => Sidebar;
        public override Color MenuStripGradientEnd => Sidebar;
        public override Color MenuItemSelected => SidebarHover;
        public override Color MenuItemBorder => Border;
        public override Color MenuBorder => Border;
        public override Color SeparatorDark => Border;
        public override Color SeparatorLight => Border;
    }
}
