namespace Anchor.Tests.TLAPlus;

using System.Diagnostics;

// The Python harnesses under tests/strands, run as part of the suite.
//
// They were hand-run only, which put them outside the discipline the rest of the specs are held to
// — a harness that stopped catching what it was written to catch would have gone unnoticed. The
// tests assert the finding each one exists to pin, not merely that it exited zero.
//
// THEY LIVE IN SIX CLASSES, not one, and the reason is measured rather than stylistic. xunit
// parallelises across collections and gives each class its own; as a single class these 29 tests
// ran serially for 507s while seven cores idled, which was the whole suite's wall clock. They are
// grouped by theme and BALANCED BY MEASURED DURATION — see each class's remarks for its share.
// The floor is the longest single test, so a new harness that dwarfs the others should be weighed
// against the class it joins rather than dropped into the smallest one.
//
// BUT REBALANCING IS NO LONGER THE LEVER, and the per-class shares below are kept for orientation
// rather than as a budget to optimise against. Measured on this machine: the suite does 1880s of
// serial work in 487s, a 3.86x speedup — and a standalone probe puts TLC's own ceiling at about
// 3x, reached by six concurrent runs and flat after eight. The machine is SATURATED. Splitting a
// class further moves the floor from 487s towards 1880/4 ≈ 470s and no lower, so it buys about 3%.
//
// WHAT THE TIME ACTUALLY IS: about 1.6s of every ~2.0s TLC run is starting a JVM, measured on a
// one-state model, so a check costs almost the same whatever it checks. ~80% of the suite's serial
// time is JVM startup. AppCDS was tried against it and rejected — 6% single-threaded, nothing at
// all under concurrency, for a 22 MB archive that would have to be regenerated per JDK.
//
// So the only lever is FEWER INVOCATIONS, which is what `src/agent/invoke.py` is: a content-keyed
// memo over the checker, because the pipeline asks identical questions several times per run. It
// deletes no check — see tests/strands/checker_memo.py for the proof that the answers are the same
// ones — and it is why several figures below now read high.
//
// FOR A DEVELOPMENT LOOP, `python tests/strands/run.py` runs the 22 harnesses directly in about
// 5m30s without building four projects first. It is not a replacement: these tests assert the
// FINDING each harness pins, and a bare exit code does not.
//
//     TranslationHarnessTests    our reading agrees with somebody else's implementation
//     VocabularyHarnessTests     what a policy's values and scope become in the model
//     VacuityHarnessTests        the derived checks — inert rules, and why
//     IntentHarnessTests         the intentional checks — properties and comparisons
//     AuthoringHarnessTests      what the agent writes, and the gates on it
//     RepairHarnessTests         the bounded repair loop
//
// This file holds what they share: the skip attribute and the runner.

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
        this.script = script;

        var why = PythonHarness.Unavailable(modules);
        if (why is not null)
        {
            Skip = $"{script}: {why}";
        }
    }

    #endregion

    #region Properties

    /// <summary>
    /// A repo-relative path to an executable the harness needs, <em>without</em> the extension —
    /// <c>.exe</c> is appended on Windows. Skipped over when it is absent.
    /// </summary>
    /// <remarks>
    /// <para>
    /// For build outputs that are not in the repo — the <c>dogwood</c> binary in particular, which
    /// has to be compiled from <c>reference/</c> and is 18 MB of it. Same reasoning as the venv
    /// check: a harness that cannot run should say so in the run summary rather than pass quietly.
    /// </para>
    /// <para>
    /// The extension is resolved here rather than at the call site because attribute arguments must
    /// be compile-time constants. Hard-coding <c>.exe</c> would skip on Linux forever — silently,
    /// and including after someone builds the binary, which is the worse half of the bug.
    /// </para>
    /// </remarks>
    public string? RequiresExecutable
    {
        get => requiresExecutable;
        set
        {
            requiresExecutable = value;

            if (Skip is null && value is not null && PythonHarness.RepoRoot is string root)
            {
                var path = OperatingSystem.IsWindows() ? $"{value}.exe" : value;

                if (!File.Exists(Path.Combine(root, path)))
                {
                    Skip = $"{script}: {path} not built";
                }
            }
        }
    }

    /// <summary>
    /// A repo-relative file or directory the harness needs. Skipped over when it is absent.
    /// </summary>
    /// <remarks>
    /// For inputs that live outside the repo — the Dogwood corpus in particular, which sits under
    /// the gitignored, machine-specific <c>reference/</c> tree and so is simply not there in CI.
    /// Unlike <see cref="RequiresExecutable"/> the value is used verbatim: no extension is appended,
    /// and a directory is as valid as a file.
    /// </remarks>
    public string? RequiresPath
    {
        get => requiresPath;
        set
        {
            requiresPath = value;

            if (Skip is null && value is not null && PythonHarness.RepoRoot is string root
                && !Path.Exists(Path.Combine(root, value)))
            {
                Skip = $"{script}: {value} not present";
            }
        }
    }

    #endregion

    #region Fields

    readonly string script;
    string? requiresExecutable;
    string? requiresPath;

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
            return "no venv at python/ — see requirements/strands/install.cmd";
        }

        var missing = modules.Where(m => !CanImport(m)).ToArray();
        return missing.Length == 0
            ? null
            : $"venv is missing {string.Join(", ", missing)} — see requirements/strands/install.cmd";
    }

    /// <summary>Run a harness, from the repo root, the way it is run by hand.</summary>
    /// <remarks>
    /// The environment is inherited, which is how <c>ANCHOR_TLC_JAVA_OPTS</c> reaches the TLC runs
    /// these harnesses spawn — set once on the test host by <c>anchor.runsettings</c>, which is
    /// also where the measurements justifying it are recorded. Running a harness by hand simply
    /// does not set it, and is slower for it.
    /// </remarks>
    public static async Task<(int ExitCode, string Output)> RunAsync(string script, params string[] args)
    {
        var info = new ProcessStartInfo(Interpreter!)
        {
            WorkingDirectory = RepoRoot!,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        info.ArgumentList.Add(script);
        foreach (var arg in args)
        {
            info.ArgumentList.Add(arg);
        }

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
