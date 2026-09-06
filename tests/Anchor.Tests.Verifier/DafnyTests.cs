namespace Anchor.Tests.Dafny;

using Anchor.Verifiers.Dafny;

public class DafnyToolTests : TestsRuntime
{
    const string Triple =
        """
        method Triple(x: int) returns (r: int)
          ensures r == 3 * x
        {
          var y := 2 * x;
          r := x + y;
        }

        method Main() {
          var t := Triple(18);
          print t, "\n"; // 54
        }
        """;

    [Fact]
    public async Task CanParse()
    {
        var r = await DafnyProgram.ParseAsync(Triple);
        Assert.True(r.IsSuccess, r.Message);
    }

    [Fact]
    public async Task CanResolve()
    {
        var r = await DafnyProgram.ResolveAsync(Triple);
        Assert.True(r.IsSuccess, r.Message);
    }

    [Fact]
    public async Task DoesNotParseSyntaxError()
    {
        var r = await DafnyProgram.ParseAsync("method Bad(x: int) returns (r: int) { r := x + }");
        Assert.False(r.IsSuccess);
        Assert.Contains("Error", r.Message);
    }

    [Fact]
    public async Task DoesNotResolveTypeError()
    {
        var r = await DafnyProgram.ResolveAsync(
            """
            method Bad(x: int) returns (r: bool) {
              r := x + 1;
            }
            """);
        Assert.False(r.IsSuccess);
        Assert.Contains("not assignable", r.Message!);
    }
}
