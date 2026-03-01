using EstimationTool.Services;

namespace EstimationTool.Forms.Panels;

partial class RequestInboxPanel
{
    private System.ComponentModel.IContainer? components = null;

    protected override void Dispose(bool disposing)
    {
        if (disposing)
            components?.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        stack = new TableLayoutPanel();
        headerPanel = new Panel();
        toolbarPanel = new Panel();
        lblFilter = new Label();
        _cmbStatusFilter = new ComboBox();
        _btnAddRequest = new Button();
        _btnRefresh = new Button();
        gridContainer = new Panel();
        _dgv = new DataGridView();
        actionBarPanel = new Panel();
        _btnCreateEstimation = new Button();
        _btnEdit = new Button();
        _btnViewDetails = new Button();
        statusBarPanel = new Panel();
        _lblStatus = new Label();
        dataGridViewTextBoxColumn1 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn2 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn3 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn4 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn5 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn6 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn7 = new DataGridViewTextBoxColumn();
        dataGridViewTextBoxColumn8 = new DataGridViewTextBoxColumn();
        stack.SuspendLayout();
        toolbarPanel.SuspendLayout();
        gridContainer.SuspendLayout();
        ((System.ComponentModel.ISupportInitialize)_dgv).BeginInit();
        actionBarPanel.SuspendLayout();
        statusBarPanel.SuspendLayout();
        SuspendLayout();
        // 
        // stack
        // 
        stack.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
        stack.Controls.Add(headerPanel, 0, 0);
        stack.Controls.Add(toolbarPanel, 0, 1);
        stack.Controls.Add(gridContainer, 0, 2);
        stack.Controls.Add(actionBarPanel, 0, 3);
        stack.Controls.Add(statusBarPanel, 0, 4);
        stack.Location = new Point(0, 0);
        stack.Name = "stack";
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 68F));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 58F));
        stack.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 56F));
        stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 30F));
        stack.Size = new Size(200, 100);
        stack.TabIndex = 0;
        // 
        // headerPanel
        // 
        headerPanel.Location = new Point(3, 3);
        headerPanel.Name = "headerPanel";
        headerPanel.Size = new Size(194, 62);
        headerPanel.TabIndex = 0;
        // 
        // toolbarPanel
        // 
        toolbarPanel.Controls.Add(lblFilter);
        toolbarPanel.Controls.Add(_cmbStatusFilter);
        toolbarPanel.Controls.Add(_btnAddRequest);
        toolbarPanel.Controls.Add(_btnRefresh);
        toolbarPanel.Location = new Point(3, 71);
        toolbarPanel.Name = "toolbarPanel";
        toolbarPanel.Size = new Size(194, 52);
        toolbarPanel.TabIndex = 1;
        // 
        // lblFilter
        // 
        lblFilter.Location = new Point(0, 0);
        lblFilter.Name = "lblFilter";
        lblFilter.Size = new Size(100, 23);
        lblFilter.TabIndex = 0;
        // 
        // _cmbStatusFilter
        // 
        _cmbStatusFilter.Items.AddRange(new object[] { "All", "NEW", "IN_ESTIMATION", "ESTIMATED", "COMPLETED" });
        _cmbStatusFilter.Location = new Point(0, 6);
        _cmbStatusFilter.Name = "_cmbStatusFilter";
        _cmbStatusFilter.Size = new Size(121, 23);
        _cmbStatusFilter.TabIndex = 1;
        // 
        // _btnAddRequest
        // 
        _btnAddRequest.Location = new Point(121, 6);
        _btnAddRequest.Name = "_btnAddRequest";
        _btnAddRequest.Size = new Size(75, 23);
        _btnAddRequest.TabIndex = 2;
        // 
        // _btnRefresh
        // 
        _btnRefresh.Location = new Point(196, 6);
        _btnRefresh.Name = "_btnRefresh";
        _btnRefresh.Size = new Size(75, 23);
        _btnRefresh.TabIndex = 3;
        // 
        // gridContainer
        // 
        gridContainer.Controls.Add(_dgv);
        gridContainer.Location = new Point(3, 129);
        gridContainer.Name = "gridContainer";
        gridContainer.Size = new Size(194, 1);
        gridContainer.TabIndex = 2;
        // 
        // _dgv
        // 
        _dgv.Columns.AddRange(new DataGridViewColumn[] { dataGridViewTextBoxColumn1, dataGridViewTextBoxColumn2, dataGridViewTextBoxColumn3, dataGridViewTextBoxColumn4, dataGridViewTextBoxColumn5, dataGridViewTextBoxColumn6, dataGridViewTextBoxColumn7, dataGridViewTextBoxColumn8 });
        _dgv.Location = new Point(0, 0);
        _dgv.Name = "_dgv";
        _dgv.Size = new Size(240, 150);
        _dgv.TabIndex = 0;
        // 
        // actionBarPanel
        // 
        actionBarPanel.Controls.Add(_btnCreateEstimation);
        actionBarPanel.Controls.Add(_btnEdit);
        actionBarPanel.Controls.Add(_btnViewDetails);
        actionBarPanel.Location = new Point(3, 17);
        actionBarPanel.Name = "actionBarPanel";
        actionBarPanel.Size = new Size(194, 50);
        actionBarPanel.TabIndex = 3;
        // 
        // _btnCreateEstimation
        // 
        _btnCreateEstimation.Location = new Point(0, 8);
        _btnCreateEstimation.Name = "_btnCreateEstimation";
        _btnCreateEstimation.Size = new Size(75, 23);
        _btnCreateEstimation.TabIndex = 0;
        // 
        // _btnEdit
        // 
        _btnEdit.Location = new Point(75, 8);
        _btnEdit.Name = "_btnEdit";
        _btnEdit.Size = new Size(75, 23);
        _btnEdit.TabIndex = 1;
        // 
        // _btnViewDetails
        // 
        _btnViewDetails.Location = new Point(150, 8);
        _btnViewDetails.Name = "_btnViewDetails";
        _btnViewDetails.Size = new Size(75, 23);
        _btnViewDetails.TabIndex = 2;
        // 
        // statusBarPanel
        // 
        statusBarPanel.Controls.Add(_lblStatus);
        statusBarPanel.Location = new Point(3, 73);
        statusBarPanel.Name = "statusBarPanel";
        statusBarPanel.Size = new Size(194, 24);
        statusBarPanel.TabIndex = 4;
        // 
        // _lblStatus
        // 
        _lblStatus.Location = new Point(0, 0);
        _lblStatus.Name = "_lblStatus";
        _lblStatus.Size = new Size(100, 23);
        _lblStatus.TabIndex = 0;
        // 
        // dataGridViewTextBoxColumn1
        // 
        dataGridViewTextBoxColumn1.Name = "dataGridViewTextBoxColumn1";
        // 
        // dataGridViewTextBoxColumn2
        // 
        dataGridViewTextBoxColumn2.Name = "dataGridViewTextBoxColumn2";
        // 
        // dataGridViewTextBoxColumn3
        // 
        dataGridViewTextBoxColumn3.Name = "dataGridViewTextBoxColumn3";
        // 
        // dataGridViewTextBoxColumn4
        // 
        dataGridViewTextBoxColumn4.Name = "dataGridViewTextBoxColumn4";
        // 
        // dataGridViewTextBoxColumn5
        // 
        dataGridViewTextBoxColumn5.Name = "dataGridViewTextBoxColumn5";
        // 
        // dataGridViewTextBoxColumn6
        // 
        dataGridViewTextBoxColumn6.Name = "dataGridViewTextBoxColumn6";
        // 
        // dataGridViewTextBoxColumn7
        // 
        dataGridViewTextBoxColumn7.Name = "dataGridViewTextBoxColumn7";
        // 
        // dataGridViewTextBoxColumn8
        // 
        dataGridViewTextBoxColumn8.Name = "dataGridViewTextBoxColumn8";
        // 
        // RequestInboxPanel
        // 
        BackColor = Color.FromArgb(30, 30, 46);
        Controls.Add(stack);
        Name = "RequestInboxPanel";
        Size = new Size(1117, 418);
        stack.ResumeLayout(false);
        toolbarPanel.ResumeLayout(false);
        gridContainer.ResumeLayout(false);
        ((System.ComponentModel.ISupportInitialize)_dgv).EndInit();
        actionBarPanel.ResumeLayout(false);
        statusBarPanel.ResumeLayout(false);
        ResumeLayout(false);
    }

    // Field declarations
    private DataGridView _dgv = null!;
    private ComboBox _cmbStatusFilter = null!;
    private Button _btnCreateEstimation = null!;
    private Button _btnEdit = null!;
    private Button _btnViewDetails = null!;
    private Button _btnAddRequest = null!;
    private Button _btnRefresh = null!;
    private Label _lblStatus = null!;
    private TableLayoutPanel stack;
    private Panel headerPanel;
    private Panel toolbarPanel;
    private Label lblFilter;
    private Panel gridContainer;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn1;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn2;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn3;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn4;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn5;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn6;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn7;
    private DataGridViewTextBoxColumn dataGridViewTextBoxColumn8;
    private Panel actionBarPanel;
    private Panel statusBarPanel;
}
