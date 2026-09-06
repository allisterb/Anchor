namespace Anchor.Tests.TLAPlus;

using Anchor.Verifiers.TLAPlus;

public class SANYTests : TestsRuntime
{
    [Fact]
    public void CanParse()
    {
        var s = SANY.Parse(Path.Combine("testfiles", "HourClock.tla"));
        Assert.True(s.IsSuccess, s.Message);
    }
}
