namespace Anchor.Verifiers.TLAPlus;

public class TLA2Tools: Runtime
{
    public static void SANY(params string[] args) => tla2sany.drivers.SANY.SANYmain(args);

    public static void TLC(params string[] args) => tlc2.TLC.main(args);
}
