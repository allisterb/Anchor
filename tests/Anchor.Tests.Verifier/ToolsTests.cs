namespace Anchor.Tests.TLAPlus;

using Anchor.Verifiers.TLAPlus;


public class ToolsTests
{
    
    [Fact]
    public void CanParse()
    {
        TLA2Tools.SANY(Path.Combine("testfiles", "HourClock.tla"));
    }

    [Fact]
    public void CanCheck()
    {
        TLA2Tools.TLC("-config", Path.Combine("testfiles", "Prisoners.cfg"), Path.Combine("testfiles", "Prisoners.tla"));
    }
}
