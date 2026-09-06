namespace Anchor.Tests.TLAPlus;

using Anchor.Verifiers.TLAPlus;

public class TLCProcessTests : TestsRuntime
{
    static string Spec(string name) => Path.Combine("testfiles", name);

    [Fact]
    public void CanFindJavaAndJar()
    {
        var java = TLCProcess.FindJava();
        Assert.True(java.IsSuccess, java.Message);
        var jar = TLCProcess.FindJar();
        Assert.True(jar.IsSuccess, jar.Message);
        Info("Running TLC from {0} on {1}.", jar.Value, java.Value);
    }

    [Fact]
    public async Task CanCheck()
    {
        var r = await TLCProcess.CheckAsync(Spec("Prisoners.tla"), Spec("Prisoners.cfg"));
        Assert.True(r.IsSuccess, r.Message);
        Assert.True(r.Value.Verified, r.Value.Output);
        Assert.Empty(r.Value.Errors);
    }

    [Fact]
    public async Task CanReportInvariantViolationWithTrace()
    {
        var r = await TLCProcess.CheckAsync(Spec("Bad.tla"), Spec("Bad.cfg"));
        Assert.True(r.IsSuccess, r.Message);
        Assert.False(r.Value.Verified);

        // The violation is identified by code, not by matching TLC's English.
        Assert.Contains(r.Value.Errors, e => e.Code == TLCCodes.InvariantViolated);

        // Init x = 0, then Next increments to 3, which breaks Inv == x < 3.
        var trace = r.Value.Trace.ToList();
        Assert.Equal(4, trace.Count);
        Assert.All(trace, s => Assert.True(s.IsState));
        Assert.Contains("x = 3", trace[^1].Text);
    }

    [Fact]
    public async Task ReportsMissingSpec()
    {
        var r = await TLCProcess.CheckAsync(Spec("NoSuchSpec.tla"));
        Assert.False(r.IsSuccess);
        Assert.Contains("could not be found", r.Message!);
    }

    [Fact]
    public void CanParseToolOutput()
    {
        var messages = TLCProcess.Parse(
            """
            @!@!@STARTMSG 2262:0 @!@!@
            TLC2 Version 2.15
            @!@!@ENDMSG 2262 @!@!@
            Parsing file Prisoners.tla
            @!@!@STARTMSG 2110:1 @!@!@
            Invariant Inv is violated.
            @!@!@ENDMSG 2110 @!@!@
            """);

        // The unframed "Parsing file" line is not a message.
        Assert.Equal(2, messages.Count);
        Assert.Equal(TLCCodes.Version, messages[0].Code);
        Assert.Equal("TLC_VERSION", messages[0].Name);
        Assert.False(messages[0].IsError);
        Assert.Equal(TLCCodes.InvariantViolated, messages[1].Code);
        Assert.True(messages[1].IsError);
        Assert.Equal("Invariant Inv is violated.", messages[1].Text);
    }
}
