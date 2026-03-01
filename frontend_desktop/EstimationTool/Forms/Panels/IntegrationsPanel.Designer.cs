using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class IntegrationsPanel
{
    private System.ComponentModel.IContainer? components = null;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    // -------------------------------------------------------------------------
    // Field-level controls — header
    // -------------------------------------------------------------------------

    private Label lblHeader = null!;

    // REDMINE card controls
    private Panel pnlCardRedmine = null!;
    private Label lblTitleRedmine = null!;
    private Panel pnlDividerRedmine = null!;
    private TableLayoutPanel tblRedmine = null!;
    private CheckBox chkEnabledRedmine = null!;
    private TextBox txtBaseUrlRedmine = null!;
    private TextBox txtApiKeyRedmine = null!;
    private TextBox txtUsernameRedmine = null!;
    private TextBox txtConfigRedmine = null!;
    private FlowLayoutPanel btnRowRedmine = null!;
    private Button btnSaveRedmine = null!;
    private Button btnTestRedmine = null!;
    private Button btnSyncRedmine = null!;
    private Label lblResultRedmine = null!;
    private Label lblLastSyncRedmine = null!;

    // JIRA card controls
    private Panel pnlCardJira = null!;
    private Label lblTitleJira = null!;
    private Panel pnlDividerJira = null!;
    private TableLayoutPanel tblJira = null!;
    private CheckBox chkEnabledJira = null!;
    private TextBox txtBaseUrlJira = null!;
    private TextBox txtApiKeyJira = null!;
    private TextBox txtUsernameJira = null!;
    private TextBox txtConfigJira = null!;
    private FlowLayoutPanel btnRowJira = null!;
    private Button btnSaveJira = null!;
    private Button btnTestJira = null!;
    private Button btnSyncJira = null!;
    private Label lblResultJira = null!;
    private Label lblLastSyncJira = null!;

    // EMAIL card controls
    private Panel pnlCardEmail = null!;
    private Label lblTitleEmail = null!;
    private Panel pnlDividerEmail = null!;
    private TableLayoutPanel tblEmail = null!;
    private CheckBox chkEnabledEmail = null!;
    private TextBox txtBaseUrlEmail = null!;
    private TextBox txtApiKeyEmail = null!;
    private TextBox txtUsernameEmail = null!;
    private TextBox txtConfigEmail = null!;
    private FlowLayoutPanel btnRowEmail = null!;
    private Button btnSaveEmail = null!;
    private Button btnTestEmail = null!;
    private Button btnSyncEmail = null!;
    private Label lblResultEmail = null!;
    private Label lblLastSyncEmail = null!;

    // Spacers / padding
    private Panel pnlSpacerAfterRedmine = null!;
    private Panel pnlSpacerAfterJira = null!;
    private Panel pnlBottomPadding = null!;

    // -------------------------------------------------------------------------
    // InitializeComponent
    // -------------------------------------------------------------------------

    private void InitializeComponent()
    {
        lblHeader = new Label();
        pnlSpacerAfterRedmine = new Panel();
        pnlSpacerAfterJira = new Panel();
        pnlBottomPadding = new Panel();
        SuspendLayout();
        // 
        // lblHeader
        // 
        lblHeader.Location = new Point(0, 0);
        lblHeader.Name = "lblHeader";
        lblHeader.Size = new Size(100, 23);
        lblHeader.TabIndex = 3;
        // 
        // pnlSpacerAfterRedmine
        // 
        pnlSpacerAfterRedmine.Location = new Point(0, 0);
        pnlSpacerAfterRedmine.Name = "pnlSpacerAfterRedmine";
        pnlSpacerAfterRedmine.Size = new Size(200, 100);
        pnlSpacerAfterRedmine.TabIndex = 2;
        // 
        // pnlSpacerAfterJira
        // 
        pnlSpacerAfterJira.Location = new Point(0, 0);
        pnlSpacerAfterJira.Name = "pnlSpacerAfterJira";
        pnlSpacerAfterJira.Size = new Size(200, 100);
        pnlSpacerAfterJira.TabIndex = 1;
        // 
        // pnlBottomPadding
        // 
        pnlBottomPadding.Location = new Point(0, 0);
        pnlBottomPadding.Name = "pnlBottomPadding";
        pnlBottomPadding.Size = new Size(200, 100);
        pnlBottomPadding.TabIndex = 0;
        // 
        // IntegrationsPanel
        // 
        AutoScroll = true;
        BackColor = Color.FromArgb(30, 30, 46);
        Controls.Add(pnlBottomPadding);
        Controls.Add(pnlSpacerAfterJira);
        Controls.Add(pnlSpacerAfterRedmine);
        Controls.Add(lblHeader);
        Name = "IntegrationsPanel";
        Padding = new Padding(16);
        Size = new Size(1143, 418);
        ResumeLayout(false);
    }

    // -------------------------------------------------------------------------
    // BuildSystemSection — creates all controls for one integration card.
    // Called once per system from InitializeComponent so that every field-level
    // variable is assigned before ResumeLayout is called.
    // -------------------------------------------------------------------------

    private void BuildSystemSection(
        string               systemName,
        out Panel            card,
        out Label            titleLabel,
        out Panel            divider,
        out TableLayoutPanel fieldGrid,
        out CheckBox         chkEnabled,
        out TextBox          txtBaseUrl,
        out TextBox          txtApiKey,
        out TextBox          txtUsername,
        out TextBox          txtConfig,
        out FlowLayoutPanel  btnRow,
        out Button           btnSave,
        out Button           btnTest,
        out Button           btnSync,
        out Label            lblResult,
        out Label            lblLastSync)
    {
        // Outer card panel
        card = new Panel
        {
            Dock      = DockStyle.Top,
            BackColor = ThemeHelper.Surface,
            Padding   = new Padding(16, 14, 16, 14),
            AutoSize  = false,
            Height    = 436,
        };
        card.Paint += PaintCardBorder;

        // System name header
        titleLabel = new Label
        {
            Text      = systemName,
            Dock      = DockStyle.Top,
            Height    = 36,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI Semibold", 12f, FontStyle.Bold),
            TextAlign = ContentAlignment.BottomLeft,
        };

        // Divider line below system name
        divider = new Panel
        {
            Dock      = DockStyle.Top,
            Height    = 2,
            BackColor = ThemeHelper.Border,
            Margin    = new Padding(0, 4, 0, 8),
        };

        // ---- Field rows using a 4-column TableLayoutPanel ----
        fieldGrid = new TableLayoutPanel
        {
            Dock         = DockStyle.Top,
            AutoSize     = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor    = Color.Transparent,
            ColumnCount  = 4,   // label | field | label | field
            RowCount     = 3,
            Padding      = new Padding(0, 8, 0, 8),
        };
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,  50f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100f));
        fieldGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,  50f));
        fieldGrid.RowStyles.Add(new RowStyle(SizeType.Absolute, 56f));  // Row 0: Enabled + Base URL
        fieldGrid.RowStyles.Add(new RowStyle(SizeType.Absolute, 56f));  // Row 1: API Key + Username
        fieldGrid.RowStyles.Add(new RowStyle(SizeType.Absolute, 96f));  // Row 2: Config JSON (multiline)

        // Row 0: Enabled | Base URL
        chkEnabled = new CheckBox
        {
            Text      = "Enabled",
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.Text,
            Font      = new Font("Segoe UI", 9.5f),
            Dock      = DockStyle.Fill,
            Margin    = new Padding(0, 6, 0, 0),
        };
        fieldGrid.Controls.Add(chkEnabled, 0, 0);
        fieldGrid.SetColumnSpan(chkEnabled, 1);

        txtBaseUrl = MakeTextBox();
        var capBaseUrl = MakeCaptionPanel("Base URL", txtBaseUrl);
        fieldGrid.Controls.Add(capBaseUrl, 1, 0);
        fieldGrid.SetColumnSpan(capBaseUrl, 3); // Base URL spans cols 1–3

        // Row 1: API Key | Username
        txtApiKey = MakeTextBox(passwordChar: true);
        var capApiKey = MakeCaptionPanel("API Key", txtApiKey);
        fieldGrid.Controls.Add(capApiKey, 0, 1);
        fieldGrid.SetColumnSpan(capApiKey, 2);

        txtUsername = MakeTextBox();
        var capUsername = MakeCaptionPanel("Username", txtUsername);
        fieldGrid.Controls.Add(capUsername, 2, 1);
        fieldGrid.SetColumnSpan(capUsername, 2);

        // Row 2: Additional Config (JSON) — spans all columns
        txtConfig = MakeTextBox(multiline: true);
        txtConfig.Height = 72;
        var capConfig = MakeCaptionPanel("Additional Config (JSON)", txtConfig);
        fieldGrid.Controls.Add(capConfig, 0, 2);
        fieldGrid.SetColumnSpan(capConfig, 4);

        // ---- Action buttons row ----
        btnRow = new FlowLayoutPanel
        {
            Dock           = DockStyle.Top,
            Height         = 50,
            BackColor      = Color.Transparent,
            FlowDirection  = FlowDirection.LeftToRight,
            WrapContents   = false,
            Padding        = new Padding(0, 6, 0, 4),
        };

        btnSave = MakeActionButton("Save");
        btnTest = MakeActionButton("Test Connection");
        btnSync = MakeActionButton("Sync Now");
        ThemeHelper.StyleButton(btnSave, isPrimary: true);
        ThemeHelper.StyleButton(btnTest, isPrimary: false);
        ThemeHelper.StyleButton(btnSync, isPrimary: false);

        btnRow.Controls.Add(btnSave);
        btnRow.Controls.Add(btnTest);
        btnRow.Controls.Add(btnSync);

        // ---- Result label (shown after Test/Sync) ----
        lblResult = new Label
        {
            Dock         = DockStyle.Top,
            Height       = 26,
            BackColor    = Color.Transparent,
            ForeColor    = ThemeHelper.TextSecondary,
            Font         = new Font("Segoe UI", 9f),
            TextAlign    = ContentAlignment.MiddleLeft,
            Text         = "",
            AutoEllipsis = true,
        };

        // ---- Last sync timestamp ----
        lblLastSync = new Label
        {
            Dock      = DockStyle.Top,
            Height    = 24,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font      = new Font("Segoe UI", 8.5f, FontStyle.Italic),
            TextAlign = ContentAlignment.MiddleLeft,
            Text      = "Last sync: never",
        };

        // Add controls in REVERSE order for DockStyle.Top stacking.
        // Desired order inside card: title → divider → fieldGrid → btnRow → lblResult → lblLastSync
        card.Controls.Add(lblLastSync);
        card.Controls.Add(lblResult);
        card.Controls.Add(btnRow);
        card.Controls.Add(fieldGrid);
        card.Controls.Add(divider);
        card.Controls.Add(titleLabel);
    }

    // -------------------------------------------------------------------------
    // Control factory helpers (support InitializeComponent)
    // -------------------------------------------------------------------------

    private static TextBox MakeTextBox(bool passwordChar = false, bool multiline = false)
    {
        var txt = new TextBox
        {
            Dock          = DockStyle.Fill,
            Multiline     = true,        // Always multiline so WinForms respects height
            WordWrap      = multiline,   // Only wrap for actual multiline fields
            ScrollBars    = multiline ? ScrollBars.Vertical : ScrollBars.None,
            AcceptsReturn = multiline,
        };
        if (!multiline) txt.Height = 28;  // Fixed height for single-line inputs
        if (passwordChar) txt.UseSystemPasswordChar = true;
        ThemeHelper.StyleTextBox(txt);
        return txt;
    }

    /// <summary>
    /// Wraps a caption label and input control into a vertical pair panel.
    /// </summary>
    private static Panel MakeCaptionPanel(string caption, Control input)
    {
        var panel = new Panel
        {
            Dock      = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding   = new Padding(0, 0, 8, 4),
        };

        var lbl = new Label
        {
            Text      = caption,
            Dock      = DockStyle.Top,
            Height    = 20,
            BackColor = Color.Transparent,
            ForeColor = ThemeHelper.TextSecondary,
            Font      = new Font("Segoe UI", 8.5f),
            TextAlign = ContentAlignment.BottomLeft,
            AutoSize  = false,
        };

        input.Dock = DockStyle.Fill;
        panel.Controls.Add(input);
        panel.Controls.Add(lbl);
        return panel;
    }

    private static Button MakeActionButton(string text)
    {
        return new Button
        {
            Text     = text,
            Height   = 36,
            AutoSize = false,
            Width    = text.Length > 10 ? 150 : 90,
            Margin   = new Padding(0, 0, 8, 0),
        };
    }

    private static void PaintCardBorder(object? sender, PaintEventArgs e)
    {
        if (sender is not Panel p) return;
        using var pen = new Pen(ThemeHelper.Border, 1f);
        e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1);
    }
}
