namespace Anchor.Tests.TLAPlus;

using System.Diagnostics;

/// <summary>
/// The Python harnesses under tests/strands, run as part of the suite.
///
/// They were hand-run only, which put them outside the discipline the rest of the specs are held to
/// — a harness that stopped catching what it was written to catch would have gone unnoticed. These
/// assert the finding each one exists to pin, not merely that it exited zero.
///
/// SKIPPED WHEN THE VENV IS ABSENT. The harnesses need the repo venv, which is installed by hand
/// (requirements/install.cmd) and which CI does not set up. Skipping is visible in the run summary;
/// a silent pass would be worse than not having the test.
/// </summary>
public class HarnessTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// Strands decides readiness per edge with OR semantics, so an unguarded join starts before all
    /// its parents are done. Both halves are pinned: unguarded graphs must violate HP10 and admit
    /// the join twice in the real SDK; guarded with <c>all_complete</c> they must verify and admit
    /// it once.
    /// </summary>
    [PythonHarness("graph_to_tla.py", "strands")]
    public async Task GraphTranslatorAgreesWithTheSdk()
    {
        var run = await PythonHarness.RunAsync("tests/strands/graph_to_tla.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("all scenarios matched expectation", run.Output);

        // Both colours, or the comparison proves nothing.
        Assert.Contains("HP10 + termination: VIOLATED", run.Output);
        Assert.Contains("HP10 + termination: HOLD", run.Output);

        // The SDK side of the same red/green. Keyed on how many times the join is admitted rather
        // than on execution order: the batch runs concurrently, so the order varies between runs.
        Assert.Contains("C ran 2x", run.Output);
        Assert.Contains("C ran 1x", run.Output);

        // The cross-model matrix, and specifically the two rows where the models disagree. Both
        // are findings in their own right and both are easy to lose to a well-meaning edit.
        Assert.DoesNotContain("! unexpected", run.Output);

        // DependencyDAG over-approximates: no batches, so it reports a violation the executor
        // cannot produce. Losing this row would mean the diamond had started failing for real.
        Assert.Matches(@"docs diamond, unguarded\s+VIOLATED\s+HOLD", run.Output);

        // And the other direction: the paper's orchestrator cancels what it cannot admit, so it
        // satisfies the property honestly, while Strands stops and reports success with a node
        // never run. A failure class DependencyDAG cannot express.
        Assert.Matches(@"router, opaque conditions\s+HOLD\s+VIOLATED", run.Output);

        // Each StrandsGraph finding attributed to the one shape that causes it. The combined
        // config cannot do this — TLC stops at the first violation, so on the skew graph
        // RunsAtMostOnce is masked by HP10 — which is why these were checked one at a time and
        // why they are pinned here rather than left as a table in a README.
        Assert.Matches(@"NoSilentSkip\s+ok\s+ok\s+VIOLATED", run.Output);
        Assert.Matches(@"HP10\s+ok\s+VIOLATED\s+ok", run.Output);
        Assert.Matches(@"RunsAtMostOnce\s+ok\s+VIOLATED\s+ok", run.Output);
    }

    /// <summary>
    /// An edge condition's TLA+ predicate has to mean what its Python does, or the annotation is the
    /// same silent-disagreement trap as a hand-written translator. The mutation matters most: a
    /// harness that cannot catch a deliberate mistranslation is checking nothing.
    /// </summary>
    [PythonHarness("condition_differential.py", "strands")]
    public async Task ConditionPredicatesAgreeWithTheirPython()
    {
        var run = await PythonHarness.RunAsync("tests/strands/condition_differential.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("matched expectation", run.Output);
        Assert.DoesNotContain("! expected", run.Output);

        // Sensitivity: the deliberately wrong predicate must still be caught.
        Assert.Contains("DISAGREE", run.Output);
        Assert.Matches(@"mistranslated.*DISAGREE", run.Output);
    }

    /// <summary>
    /// Our TLA+ reading of Dogwood's temporal operators — <c>formerly</c>, <c>previous</c> and
    /// <c>since</c>, combined with <c>&amp;&amp;</c> and <c>!</c> — against the reference
    /// implementation's own regression corpus, whose cases pair policies and traces with the
    /// verdicts their engine actually produced.
    /// </summary>
    /// <remarks>
    /// This closes the largest caveat on <c>specs/TemporalPolicy</c>: that it modelled the
    /// documented rules with nothing checking the reading was right. Nothing is built or run from
    /// the Dogwood tree — the expected outputs are recorded, so the corpus is usable as data, and
    /// this stays inside the suite's no-network property.
    /// <para>
    /// The refusal count matters as much as the agreement count. A translator that quietly
    /// mishandles a construct produces a disagreement it cannot attribute, so anything outside the
    /// modelled subset is refused. It already caught one: a case whose <c>event.dwschema</c> pins
    /// <c>callerPrincipal</c> into every predicate, making the policy mean something its own text
    /// never says.
    /// </para>
    /// </remarks>
    [PythonHarness("dogwood_differential.py")]
    public async Task DogwoodSemanticsAgreeWithTheReferenceCorpus()
    {
        var run = await PythonHarness.RunAsync("tests/strands/dogwood_differential.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("agrees with the reference", run.Output);
        Assert.DoesNotContain("DISAGREEMENT", run.Output);

        // Enough cases to be worth something. If the subset silently narrowed — a parser change
        // refusing more than it did — this notices rather than reporting a hollow success.
        var m = System.Text.RegularExpressions.Regex.Match(run.Output, @"checked\s+(\d+) \(trace");
        Assert.True(m.Success, run.Output);
        Assert.True(int.Parse(m.Groups[1].Value) >= 450,
                    $"only {m.Groups[1].Value} pairs checked\n{run.Output}");
    }

    /// <summary>
    /// The TLA+ model of Cedar against the real engine, over the whole finite request space.
    /// </summary>
    [PythonHarness("cedar_differential.py", "cedarpy")]
    public async Task CedarModelAgreesWithTheRealEngine()
    {
        var run = await PythonHarness.RunAsync("tests/strands/cedar_differential.py");
        Assert.True(run.ExitCode == 0, run.Output);
        Assert.Contains("AGREE on all", run.Output);
        Assert.DoesNotContain("DISAGREE", run.Output);
    }

    /// <summary>
    /// Bug3 reaching the real SDK: several agents on one budget, with both ledgers. The reserving
    /// one stays inside the budget; the naive check-then-charge one does not.
    /// </summary>
    /// <remarks>
    /// Asserts the shape rather than the overspend figure. The race is an interleaving, and pinning
    /// an exact number would be pinning one instance of it.
    /// </remarks>
    [PythonHarness("shared_budget.py", "strands")]
    public async Task NaiveLedgerOverspendsTheSharedBudget()
    {
        var run = await PythonHarness.RunAsync("tests/strands/shared_budget.py");
        Assert.True(run.ExitCode == 0, run.Output);
        Assert.Contains("budget respected", run.Output);
        Assert.Contains("budget VIOLATED", run.Output);
    }

    #endregion
}

/// <summary>
/// A <see cref="FactAttribute"/> that skips itself when the repo venv cannot run the harness.
///
/// The skip is decided at discovery, which is the only dynamic skip xunit v2 offers without another
/// package — and packages are installed by hand here, never automatically.
/// </summary>
[AttributeUsage(AttributeTargets.Method)]
public sealed class PythonHarnessAttribute : FactAttribute
{
    #region Constructors

    /// <param name="script">Named only for the skip message, so the reason says which harness.</param>
    /// <param name="modules">Python modules the harness imports. All must be importable.</param>
    public PythonHarnessAttribute(string script, params string[] modules)
    {
        var why = PythonHarness.Unavailable(modules);
        if (why is not null)
        {
            Skip = $"{script}: {why}";
        }
    }

    #endregion
}

/// <summary>Locates the repo venv and runs a harness script from the repo root.</summary>
public static class PythonHarness
{
    #region Properties

    /// <summary>The repo root, found by walking up to Anchor.sln. Null if the walk fails.</summary>
    public static string? RepoRoot { get; } = FindRepoRoot();

    /// <summary>
    /// The interpreter in the repo venv — <em>only</em> that one, unlike SpecTests.FindPython, which
    /// accepts any Python because the code it runs needs no third-party packages. These harnesses
    /// import strands and cedarpy, so a system interpreter would not do.
    /// </summary>
    public static string? Interpreter { get; } = FindVenvInterpreter();

    #endregion

    #region Methods

    /// <summary>Why the harness cannot run, or null if it can.</summary>
    public static string? Unavailable(params string[] modules)
    {
        if (RepoRoot is null)
        {
            return "could not locate the repo root";
        }
        if (Interpreter is null)
        {
            return "no venv at python/ — see requirements/install.cmd";
        }

        var missing = modules.Where(m => !CanImport(m)).ToArray();
        return missing.Length == 0
            ? null
            : $"venv is missing {string.Join(", ", missing)} — see requirements/install.cmd";
    }

    /// <summary>Run a harness, from the repo root, the way it is run by hand.</summary>
    public static async Task<(int ExitCode, string Output)> RunAsync(string script)
    {
        var info = new ProcessStartInfo(Interpreter!)
        {
            WorkingDirectory = RepoRoot!,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        info.ArgumentList.Add(script);

        using var process = Process.Start(info)!;

        // Read both pipes before waiting. A harness that fills one while we block on the other
        // deadlocks, and these print a lot.
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        var stdout = await stdoutTask;
        var stderr = await stderrTask;

        // Generous: graph_to_tla runs six TLC checks and two live graphs.
        using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(10));
        try
        {
            await process.WaitForExitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            throw new TimeoutException($"{script} did not finish within 10 minutes");
        }

        return (process.ExitCode, stdout + stderr);
    }

    static string? FindRepoRoot()
    {
        var dir = new DirectoryInfo(Anchor.Runtime.AssemblyLocation);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "Anchor.sln")))
        {
            dir = dir.Parent;
        }
        return dir?.FullName;
    }

    static string? FindVenvInterpreter()
    {
        if (RepoRoot is null)
        {
            return null;
        }

        var bin = Path.Combine(RepoRoot, "python", OperatingSystem.IsWindows() ? "Scripts" : "bin");
        var names = OperatingSystem.IsWindows() ? ["python.exe"] : new[] { "python3", "python" };

        return names.Select(n => Path.Combine(bin, n)).FirstOrDefault(File.Exists);
    }

    /// <summary>Importable, not merely installed — a broken install is not a usable one.</summary>
    static bool CanImport(string module) => imports.GetOrAdd(module, m =>
    {
        try
        {
            var info = new ProcessStartInfo(Interpreter!)
            {
                WorkingDirectory = RepoRoot!,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            info.ArgumentList.Add("-c");
            info.ArgumentList.Add($"import {m}");

            using var process = Process.Start(info)!;
            process.WaitForExit(milliseconds: 60_000);
            return process.HasExited && process.ExitCode == 0;
        }
        catch
        {
            return false;
        }
    });

    #endregion

    #region Fields

    // Discovery constructs one attribute per test, and several name the same module.
    static readonly System.Collections.Concurrent.ConcurrentDictionary<string, bool> imports = new();

    #endregion
}
