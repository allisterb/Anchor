namespace Anchor.Tests.MCPServer;

using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;

using Anchor.Verifiers.TLAPlus;

/// <summary>
/// <c>anchor check</c>, run as a process, held to its documented exit codes.
/// </summary>
/// <remarks>
/// <para>
/// The exit code is the part a script branches on, and it is the part nothing else tests: every
/// other route into the checker returns a <c>PolicyCheckResult</c>, where "answered" and "a claim
/// is broken" are separate fields that cannot be confused. Through a process they collapse onto one
/// integer, and the CLI is where that mapping could be wrong.
/// </para>
/// <para>
/// The mapping is deliberately the checker's own, so that <c>anchor check</c> and the Python entry
/// point can be swapped in a script:
/// 0 answered, 1 a property is BROKEN, 2 no verdict, 3 the checker could not run at all.
/// </para>
/// </remarks>
public class CliCheckTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// A finding is not an error. A DEAD forbid is the most alarming thing this fixture contains
    /// and it still exits 0, because the run ANSWERED.
    /// </summary>
    [CliPolicyFact]
    public async Task AFindingExitsZeroAndPrintsTheVerdicts()
    {
        var (exit, stdout, _) = await RunAsync("check", "tests/policies/dead_forbid.dw");

        Assert.Equal(0, exit);
        Assert.Contains("permit #1", stdout);
        Assert.Contains("DEAD", stdout);

        // The caveat that makes the verdict honest travels with it.
        Assert.Contains("UNPINNED", stdout, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// A violated `--property` claim exits 1 — the one outcome that is genuinely an error to a
    /// script, and the most useful answer the checker gives.
    /// </summary>
    [CliPolicyFact]
    public async Task ABrokenPropertyExitsOne()
    {
        var (broken, stdout, _) = await RunAsync(
            "check", "tests/policies/firewall_open.dw", "--property", "tests/policies/firewall.tla");

        Assert.Equal(1, broken);
        Assert.Contains("BROKEN", stdout);
        Assert.Contains("external", stdout);

        // And the same property against the policy it was written for holds, so the 1 above is
        // about the policy rather than about the harness.
        var (held, heldOut, _) = await RunAsync(
            "check", "tests/policies/firewall.dw", "--property", "tests/policies/firewall.tla");

        Assert.Equal(0, held);
        Assert.Contains("every claim holds", heldOut);
    }

    /// <summary>
    /// A refusal exits 2 and says why on stderr — distinct from 0, because no verdict was reached
    /// and "no findings" would be the wrong thing for a script to conclude.
    /// </summary>
    [CliPolicyFact]
    public async Task ARefusalExitsTwoAndExplainsItselfOnStderr()
    {
        var (exit, _, stderr) = await RunAsync("check", "tests/policies/like_impossible.dw");

        Assert.Equal(2, exit);
        Assert.Contains("REFUSED", stderr);
        Assert.Contains("glob intersection", stderr);
    }

    /// <summary>A missing file is also "no verdict", not a crash.</summary>
    [CliPolicyFact]
    public async Task AMissingPolicyExitsTwo()
    {
        var (exit, _, stderr) = await RunAsync("check", "tests/policies/no_such_policy.dw");

        Assert.Equal(2, exit);
        Assert.Contains("no such policy file", stderr);
    }

    /// <summary>
    /// Naming no policy is a usage error, and says so rather than producing a stack trace.
    /// </summary>
    /// <remarks>
    /// The message is System.CommandLine's; the EXIT CODE is ours. The library defaults a parse
    /// error to 1, which here already means "a --property claim is BROKEN", so a script could not
    /// have told "you typed it wrong" from "the policy does not mean what you said it means". That
    /// override is the thing this test is really guarding.
    /// </remarks>
    [CliFact]
    public async Task NamingNoPolicyIsAUsageError()
    {
        var (exit, _, stderr) = await RunAsync("check");

        Assert.Equal(2, exit);
        Assert.Contains("required value not bound to option name is missing", stderr);
    }

    /// <summary>An unknown verb does not silently start the server.</summary>
    [CliFact]
    public async Task AnUnknownVerbIsRefused()
    {
        var (exit, stdout, stderr) = await RunAsync("frobnicate");

        Assert.Equal(2, exit);
        Assert.Contains("Unrecognised command", stderr);
        Assert.Contains("frobnicate", stderr);
        Assert.Empty(stdout);
    }

    static async Task<(int Exit, string Stdout, string Stderr)> RunAsync(params string[] args)
    {
        var info = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = StdioTransportTests.Repo,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        info.ArgumentList.Add(StdioTransportTests.CliDll);
        foreach (var arg in args)
        {
            info.ArgumentList.Add(arg);
        }

        using var process = Process.Start(info)!;

        // Both pipes read before waiting: a run that fills one while we block on the other
        // deadlocks, and a verbose check prints a great deal.
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromMinutes(5));
        try
        {
            await process.WaitForExitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            throw new TimeoutException($"anchor {string.Join(' ', args)} did not finish in 5 minutes");
        }

        return (process.ExitCode, await stdout, await stderr);
    }

    #endregion
}

/// <summary>A fact needing the built CLI and the checker's toolchain: an interpreter and a JVM.</summary>
[AttributeUsage(AttributeTargets.Method)]
public sealed class CliPolicyFactAttribute : FactAttribute
{
    public CliPolicyFactAttribute()
    {
        var python = PythonProcess.FindPython();
        var java = TLCProcess.FindJava();

        Skip = !File.Exists(StdioTransportTests.CliDll)
                   ? $"the anchor CLI is not built at {StdioTransportTests.CliDll} — build the solution first"
             : !python.IsSuccess ? $"the policy checker needs Python: {python.Message}"
             : !java.IsSuccess ? $"the policy checker needs a JVM to run TLC: {java.Message}"
             : null!;
    }
}
