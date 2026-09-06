namespace Anchor.Tests.TLAPlus;

using Anchor.Verifiers.TLAPlus;

public class SANYTests
{
    [Fact]
    public void CanParse()
    {
        var s = SANY.Parse(Path.Combine("testfiles", "HourClock.tla"));
        Assert.True(s.IsSuccess);
    }

    [Fact]
    public void CanCheck()
    {
        var s = TLC.Check(Path.Combine("testfiles", "Prisoners.tla"), Path.Combine("testfiles", "Prisoners.cfg"));
        Assert.True(s.IsSuccess);
    }
}
