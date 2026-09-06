namespace Anchor.Verifiers.TLAPlus;

/// <summary>
/// Raw tla2tools driver entry points. Output goes to the console; nothing is returned.
///
/// There is deliberately no TLC counterpart: tlc2.TLC.main ends in System.exit, which would take the
/// host process with it, and TLC cannot run under IKVM regardless — see <see cref="TLCProcess"/>.
/// </summary>
public class TLA2Tools : Runtime
{
    public static void SANY(params string[] args) => tla2sany.drivers.SANY.SANYmain(args);
}
