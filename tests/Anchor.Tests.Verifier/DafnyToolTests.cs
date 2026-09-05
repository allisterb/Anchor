using Anchor.Verifiers.Dafny;

namespace Anchor.Tests.Dafny;

public class DafnyToolTests
{               
    [Fact]
    public async Task CanResolve()
    {
        var src =
            """
            method Triple(x: int) returns (r: int) {
              var y := 2 * x;
              r := x + y;
            }

            method Main() {
              var t := Triple(18);
              print t, "\n"; // 54
                            
            """;
        var o = await DafnyTool.Resolve(src);
        Assert.Equal(2, o.ExitCode);
        Assert.NotNull(o.StdOut);
    }
}
