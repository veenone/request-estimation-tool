using EstimationTool.Forms.Panels;

namespace EstimationTool.Forms.Panels.WizardSteps;

public partial class Step5PrFixes : UserControl
{
    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private readonly WizardPanel.WizardState _state;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    public Step5PrFixes(WizardPanel.WizardState state)
    {
        _state = state;

        InitializeComponent();

        // Wire value-change events
        _nudSimple.ValueChanged  += (_, _) => UpdateTotal();
        _nudMedium.ValueChanged  += (_, _) => UpdateTotal();
        _nudComplex.ValueChanged += (_, _) => UpdateTotal();

        PopulateFromState();
    }

    // -------------------------------------------------------------------------
    // Logic
    // -------------------------------------------------------------------------

    private void UpdateTotal()
    {
        int simple  = (int)_nudSimple.Value;
        int medium  = (int)_nudMedium.Value;
        int complex = (int)_nudComplex.Value;

        double total = simple * 2.0 + medium * 4.0 + complex * 8.0;
        _lblTotal.Text = $"Total PR effort:  {total:F0} h  " +
                         $"({simple}×2h + {medium}×4h + {complex}×8h)";
    }

    private void PopulateFromState()
    {
        _nudSimple.Value  = Math.Min(_nudSimple.Maximum,  Math.Max(0, _state.PrSimple));
        _nudMedium.Value  = Math.Min(_nudMedium.Maximum,  Math.Max(0, _state.PrMedium));
        _nudComplex.Value = Math.Min(_nudComplex.Maximum, Math.Max(0, _state.PrComplex));
        UpdateTotal();
    }

    // -------------------------------------------------------------------------
    // Public interface
    // -------------------------------------------------------------------------

    public void SaveToState(WizardPanel.WizardState state)
    {
        state.PrSimple  = (int)_nudSimple.Value;
        state.PrMedium  = (int)_nudMedium.Value;
        state.PrComplex = (int)_nudComplex.Value;
    }
}
