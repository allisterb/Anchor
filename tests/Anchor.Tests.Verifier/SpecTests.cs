namespace Anchor.Tests.TLAPlus;

using Anchor.Verifiers.Dafny;
using Anchor.Verifiers.TLAPlus;

/// <summary>
/// The specs under specs/ are the seed of Milestone 2: one agent workflow, verified, alongside two
/// variants each carrying one realistic mistake.
///
/// The bug variants are the load-bearing half. A verifier that reports success is only worth
/// something if it also reports failure when there is one, so these assert that TLC catches each
/// mistake and says which — by message code rather than by matching its English.
/// </summary>
public class SpecTests : TestsRuntime
{
    static string Spec(string name) => Path.Combine("specs", name);

    static async Task<TLCRun> CheckAsync(string name)
    {
        var r = await TLCProcess.CheckAsync(Spec($"{name}.tla"), Spec($"{name}.cfg"));
        Assert.True(r.IsSuccess, r.Message);
        return r.Value;
    }

    /// <summary>One spec, a config that does not share its name — several models of one module.</summary>
    static async Task<TLCRun> CheckAsync(string tla, string cfg)
    {
        var r = await TLCProcess.CheckAsync(Spec($"{tla}.tla"), Spec($"{cfg}.cfg"));
        Assert.True(r.IsSuccess, r.Message);
        return r.Value;
    }

    /// <summary>
    /// The budget is never exceeded and the task always ends — for every behaviour of a model that
    /// is free to fail forever and charge the maximum every time.
    /// </summary>
    [Fact]
    public async Task BoundedRetryVerifies()
    {
        var run = await CheckAsync("BoundedRetry/BoundedRetry");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// Checking `spent &lt; Budget` instead of `spent + MaxCost &lt;= Budget` reads like a reasonable
    /// "have I got budget left?" and overshoots by up to MaxCost - 1.
    /// </summary>
    [Fact]
    public async Task OvershootViolatesTheBudgetInvariant()
    {
        var run = await CheckAsync("BoundedRetry/Bug1_Overshoot");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);
        Assert.Contains("BudgetSafe", string.Join("\n", run.Errors.Select(e => e.Text)));

        // The counterexample walks the budget up to the last affordable-looking point and then
        // commits more than remains.
        Assert.NotEmpty(run.Trace);
        Assert.Contains("reserved = 3", run.Trace.Last().Text);
    }

    /// <summary>
    /// A clarification round that never reaches the model is not charged, so the agent can cycle
    /// forever without spending. Every safety property still holds — nothing is overspent because
    /// nothing is spent — and only liveness fails, which is what makes this class of bug invisible
    /// to an invariant-only checker.
    /// </summary>
    [Fact]
    public async Task FreeRetryViolatesTerminationButNotSafety()
    {
        var run = await CheckAsync("BoundedRetry/Bug2_FreeRetry");
        Assert.False(run.Verified);

        // Liveness, not safety: no invariant is broken.
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.TemporalPropertyViolated);
        Assert.DoesNotContain(run.Errors, e => e.Code == TLCCodes.InvariantViolated);

        // TLC closes the trace with "Back to state", which is what makes it an infinite cycle
        // rather than a finite path to a bad state.
        Assert.Contains(run.Messages, m => m.Code == TLCCodes.BackToState);
    }

    #region Shared budget

    /// <summary>Acquiring the reservation atomically leaves no window to race in.</summary>
    [Fact]
    public async Task SharedBudgetVerifies()
    {
        var run = await CheckAsync("SharedBudget/SharedBudget");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// The case Dafny cannot reach. Every agent checks before it spends and no agent overspends on
    /// its own; the budget is broken only by the order the two are interleaved in. Verifying the
    /// agents one at a time — which is all a loop invariant can do — finds nothing here.
    /// </summary>
    [Fact]
    public async Task CheckThenReserveRacesOnTheSharedBudget()
    {
        var run = await CheckAsync("SharedBudget/Bug3_CheckThenReserve");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);
        Assert.Contains("BudgetSafe", string.Join("\n", run.Errors.Select(e => e.Text)));

        // The race window itself: both agents past the check, neither yet reserved. Each is acting
        // on an affordability decision that was true when taken and is about to stop being true.
        Assert.Contains(run.Trace, s =>
            s.Text.Contains("a1 :> \"checked\"") && s.Text.Contains("a2 :> \"checked\""));
    }

    #endregion

    #region Task lifecycle

    /// <summary>
    /// The lifecycle from arXiv:2510.14133 Table 2, with TL4 weakened. Twelve properties, checked —
    /// which the paper never does; its conclusion defers verification to future work.
    /// </summary>
    [Fact]
    public async Task TaskLifecycleVerifies()
    {
        var run = await CheckAsync("TaskLifecycle/TaskLifecycle");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// TL4 exactly as published does not hold. It says a DISPATCHING task eventually reaches
    /// IN_PROGRESS, which forbids cancelling one mid-dispatch — and cancellation of in-flight work
    /// is something real frameworks do, Strands included via <c>agent.cancel()</c>.
    /// </summary>
    [Fact]
    public async Task PublishedTL4ForbidsCancellingADispatchingTask()
    {
        var r = await TLCProcess.CheckAsync(Spec("TaskLifecycle/TaskLifecycle.tla"), Spec("TaskLifecycle/TaskLifecycle_TL4Published.cfg"));
        Assert.True(r.IsSuccess, r.Message);
        Assert.False(r.Value.Verified);
        Assert.Contains(r.Value.Errors, e => e.Code == TLCCodes.TemporalPropertyViolated);

        // The counterexample is Dispatch then Cancel.
        Assert.Contains(r.Value.Trace, s => s.Text.Contains("DISPATCHING"));
        Assert.Contains(r.Value.Trace, s => s.Text.Contains("CANCELED"));
    }

    /// <summary>
    /// TL1 is not a property of the lifecycle on its own — it is a constraint on the retry policy,
    /// which the paper leaves unspecified ("if the retry policy permits"). Remove the budget and
    /// the task retries forever.
    /// </summary>
    [Fact]
    public async Task UnboundedRetryBreaksTermination()
    {
        var run = await CheckAsync("TaskLifecycle/Bug4_UnboundedRetry");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.TemporalPropertyViolated);

        // A lasso, not a finite path to a bad state: the retry cycle repeats forever.
        Assert.Contains(run.Messages, m => m.Code == TLCCodes.BackToState);
    }

    #endregion

    #region Temporal policy vacuity

    /// <summary>
    /// A session-aware permit that can actually grant something. The witness is the point: TLC
    /// reaches a state where <c>p_sell</c> fires, in two attempts — approve, then sell.
    /// </summary>
    /// <remarks>
    /// <c>NeverFires</c> is checked as an invariant and is MEANT to be violated. TLA+ is
    /// linear-time and has no <c>EF</c>, so reachability is posed as the negation of an invariant
    /// and the counterexample is read as the witness. Here that workaround is the whole tool.
    /// </remarks>
    [Fact]
    public async Task TemporalPermitIsSatisfiable()
    {
        var run = await CheckAsync("TemporalPolicy/TemporalPolicy");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);
        Assert.Contains("NeverFires", string.Join("\n", run.Errors.Select(e => e.Text)));

        // The witness ends with the permit having granted something.
        Assert.Contains(run.Trace, s => s.Text.Contains("p_sell"));
    }

    /// <summary>
    /// Forbidding the approval action makes the sell permit unsatisfiable — and nothing about
    /// either policy, read on its own, says so.
    /// </summary>
    /// <remarks>
    /// A temporal condition matching <c>Action::response</c> matches only actions that were
    /// permitted; a denied one is recorded as an <c>error</c> event. So the SellShares permit —
    /// untouched, still valid, still deployed — can never fire once approvals are forbidden. The
    /// capability it exists to grant is silently gone.
    /// <para>
    /// <b>This test passing means TLC found no violation, and that is the finding.</b> Vacuity is
    /// the absence of a witness, so the quiet result is the bad one. That inversion is why the
    /// assertion below is on <c>Verified</c> being true — the opposite of every other spec here.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task ForbiddingApprovalMakesTheSellPermitVacuous()
    {
        var run = await CheckAsync("TemporalPolicy/TemporalPolicy",
                                   "TemporalPolicy/Vacuous_ForbiddenApproval");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// The same rule gated on <c>::request</c> instead of <c>::response</c> survives the same
    /// forbid — and that is worse, not better.
    /// </summary>
    /// <remarks>
    /// AgentCore records a <c>request</c> event for every attempt, permitted or not; only the
    /// outcome event differs (<c>response</c> when allowed, <c>error</c> when denied). So a gate
    /// written against <c>::request</c> means "somebody TRIED to get an approval", and opens on
    /// attempts that were all refused. One word apart from the test above, opposite outcome, and
    /// the permit grants exactly the capability the approval existed to protect.
    /// <para>
    /// Both results come from the same engine and the same policy set, which is what makes the
    /// pair meaningful: it is the event kind doing the work, not a difference in the model.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task RequestGatedPermitFiresOnDeniedAttempts()
    {
        var run = await CheckAsync("TemporalPolicy/TemporalPolicy",
                                   "TemporalPolicy/RequestGated_SurvivesForbid");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);

        // The witness records the denied approval as an error, and sells anyway.
        Assert.Contains(run.Trace, s => s.Text.Contains("error"));
        Assert.Contains(run.Trace, s => s.Text.Contains("p_sell_request"));
    }

    #endregion

    #region Session rotation

    /// <summary>
    /// A caller who controls the session id walks straight past an aggregate cap: trade under the
    /// limit, start a new session, trade again. The engine only ever sees one session's history.
    /// </summary>
    /// <remarks>
    /// AWS documents the behaviour — "a temporal rate limit constrains activity within a session
    /// rather than across all of a caller's sessions" — so this is not a discovery. What it adds is
    /// the trace, and the finding that policy *shapes* split on it: see the two tests below.
    /// </remarks>
    [Fact]
    public async Task SessionRotationDefeatsAnAggregateCap()
    {
        var run = await CheckAsync("TemporalPolicy/SessionRotation",
                                   "TemporalPolicy/SessionRotation");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);
        Assert.Contains("GlobalCapHolds", string.Join("\n", run.Errors.Select(e => e.Text)));

        // The shape, not the instance: the history is emptied at least once on the way.
        Assert.Contains(run.Trace, s => s.Text.Contains("hist = <<>>"));
    }

    /// <summary>
    /// The control. Same policy, same adversary, rotation disabled — and the cap holds.
    /// </summary>
    /// <remarks>
    /// This pair is only meaningful together. Without it, the violation above could be any
    /// modelling error rather than rotation; with it, rotation is the one thing that differs.
    /// </remarks>
    [Fact]
    public async Task WithoutRotationTheAggregateCapHolds()
    {
        var run = await CheckAsync("TemporalPolicy/SessionRotation",
                                   "TemporalPolicy/NoRotation_CapHolds");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// The same move against an approval gate achieves nothing — it costs the caller the
    /// capability instead.
    /// </summary>
    /// <remarks>
    /// The asymmetry, and the part that is not written down anywhere. On a fresh trajectory the
    /// history is empty, so a <b>permit</b> gated on a prior event does not fire and the request is
    /// denied by default: it fails <i>closed</i>. A <b>forbid</b> on an aggregate sees a count of
    /// zero, does not fire, and the request is allowed: it fails <i>open</i>.
    /// <para>
    /// Budget caps, rate limits and mutual-exclusion rules are all the second shape.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task RotationCannotDefeatAnApprovalGate()
    {
        var run = await CheckAsync("TemporalPolicy/SessionRotation",
                                   "TemporalPolicy/Rotation_ApprovalGateHolds");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    #endregion

    #region Strands execution loop

    /// <summary>
    /// The Strands graph executor as it actually runs — batch, await the whole batch, recompute
    /// readiness, fail fast, stop when nothing is ready. On the guarded workflow all four
    /// invariants hold and the run always ends.
    /// </summary>
    /// <remarks>
    /// Separate from <c>DependencyDAG</c> because they model different orchestrators.
    /// DependencyDAG is the Host Agent of arXiv:2510.14133, which cancels orphaned subgraphs and
    /// requires every task to terminate. Strands does neither: no CANCELED status, fail-fast on a
    /// raise, and the loop simply stops when nothing is ready — leaving unadmitted nodes unrun and
    /// reporting success. The workflow-shaped counterexamples for each are in
    /// <c>tests/strands/graph_to_tla.py</c>, which checks both models against one graph.
    /// </remarks>
    [Fact]
    public async Task StrandsGraphVerifies()
    {
        var run = await CheckAsync("StrandsGraph/StrandsGraph");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    #endregion

    #region Dependency DAG

    /// <summary>
    /// HP10 from arXiv:2510.14133 Table 1: a sub-task is invoked only once every dependency has
    /// completed. Holds, together with termination — but on two conditions, neither of which the
    /// Strands runtime supplies by itself.
    /// <para>
    /// The orchestrator cancels the subgraph orphaned by a failure, or termination breaks — that is
    /// Bug5 below. And the join in <c>Workflow.tla</c> carries a condition, or HP10 breaks: Strands
    /// decides readiness per edge with OR semantics, so an unguarded join starts as soon as one
    /// parent completes. <c>tests/strands/graph_to_tla.py</c> checks an unguarded graph built from
    /// the live SDK and reports exactly that violation.
    /// </para>
    /// </summary>
    [Fact]
    public async Task DependencyDAGVerifies()
    {
        var run = await CheckAsync("DependencyDAG/DependencyDAG");
        Assert.True(run.Verified, run.Output);
        Assert.Empty(run.Errors);
    }

    /// <summary>
    /// HP10 and TL1 are not independent. Drop failure propagation and a task whose dependency
    /// failed waits forever — HP10 is still satisfied, nothing unsafe happens, and the graph simply
    /// never finishes. An orchestrator audited against HP10 alone would pass this and then hang on
    /// the first failed sub-task.
    /// </summary>
    [Fact]
    public async Task WithoutFailurePropagationTheGraphNeverFinishes()
    {
        var run = await CheckAsync("DependencyDAG/Bug5_NoFailurePropagation");
        Assert.False(run.Verified);

        // Liveness only. HP10 itself is never violated, which is the whole point.
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.TemporalPropertyViolated);
        Assert.DoesNotContain(run.Errors, e => e.Code == TLCCodes.InvariantViolated);

        // The stuck shape, and nothing more specific than that: some task has FAILED while another
        // is still BLOCKED behind it.
        //
        // No task is named. TLC may report any counterexample it reaches first, and this bug has
        // several — t3 stranded behind a failed t1 or t2, or t4 stranded behind a failed t3.
        // Successive versions of this assertion named t1, then t3, and each was flaky until the
        // assertion described the shape instead of one instance of it.
        Assert.Contains(run.Trace, s =>
            s.Text.Contains("\"FAILED\"") && s.Text.Contains("\"BLOCKED\""));
    }

    #endregion

    #region Dafny

    static async Task<DafnyVerification> VerifyAsync(string name)
    {
        var src = await File.ReadAllTextAsync(Spec(name));
        var r = await DafnyProgram.VerifyAsync(src, name);
        Assert.True(r.IsSuccess, r.Message);
        return r.Value;
    }

    /// <summary>The executable form of BoundedRetry.tla discharges the same two obligations.</summary>
    [Fact]
    public async Task BoundedRetryImplementationVerifies()
    {
        var run = await VerifyAsync("BoundedRetry/BoundedRetry.dfy");
        Assert.True(run.Verified, run.Output);
    }

    /// <summary>
    /// The free-retry bug again, in the other tool. TLC reports it as a lasso; Dafny rejects the
    /// termination measure. Both are the same claim — that every pass consumes something.
    /// </summary>
    [Fact]
    public async Task FreeRetryFailsTerminationButNotSafety()
    {
        var run = await VerifyAsync("BoundedRetry/BoundedRetryFreeRetry.dfy");
        Assert.False(run.Verified);

        // Termination is what fails.
        Assert.Contains("decreases expression might not decrease", run.Output);

        // And only termination. The budget postconditions still hold, because a round that spends
        // nothing cannot overspend — which is precisely why an invariant-only checker misses this.
        Assert.DoesNotContain("postcondition", run.Output);
        Assert.DoesNotContain("invariant", run.Output);
    }

    /// <summary>Binding the model to Python changes nothing about the proof.</summary>
    [Fact]
    public async Task ExternVariantStillVerifies()
    {
        var run = await VerifyAsync("BoundedRetry/BoundedRetryExtern.dfy");
        Assert.True(run.Verified, run.Output);
    }

    /// <summary>
    /// The extern names decide the emitted call. Dafny also writes the <c>import</c>, which the
    /// reference manual says it cannot do — it can, when the module itself is <c>{:extern}</c>.
    /// </summary>
    [Fact]
    public async Task ExternTranslatesToAPythonCall()
    {
        var src = await File.ReadAllTextAsync(Spec("BoundedRetry/BoundedRetryExtern.dfy"));
        var r = await DafnyProgram.TranslateToPythonAsync(src, "BoundedRetryExtern.dfy");
        Assert.True(r.IsSuccess, r.Message);

        var generated = r.Value.Files["module_.py"];
        Assert.Contains("import anchor_model", generated);
        Assert.Contains("anchor_model.Model.attempt(", generated);

        // The placeholder Dafny emits for the extern module is empty — it is what the real
        // implementation replaces, not something to build on.
        Assert.DoesNotContain("def attempt", r.Value.Files["anchor_model.py"]);
    }

    /// <summary>
    /// The audit is the trust boundary, enumerated. Both entries are the model, and there is
    /// nothing else — no stray assume, no unproved lemma hiding behind the budget guarantee.
    /// </summary>
    [Fact]
    public async Task AuditReportsExactlyTheModelBoundary()
    {
        var src = await File.ReadAllTextAsync(Spec("BoundedRetry/BoundedRetryExtern.dfy"));
        var r = await DafnyProgram.AuditAsync(src, "BoundedRetryExtern.dfy");
        Assert.True(r.IsSuccess, r.Message);

        Assert.False(r.Value.IsFullyProved);
        Assert.All(r.Value.Assumptions, a => Assert.Equal("Attempt", a.Declaration));
        Assert.Contains(r.Value.Assumptions, a => a.Issue.Contains("ensures"));
        Assert.Contains(r.Value.Assumptions, a => a.Issue.Contains("requires"));
        Assert.Equal(2, r.Value.Assumptions.Count);
    }

    /// <summary>
    /// A bodiless declaration is an assumption too, even without <c>{:extern}</c> — and the auditor
    /// distinguishes the ones that matter. `Attempt` carries an ensures the proof leans on, so it
    /// is reported; `NeedsClarification` promises nothing, so it is not.
    /// </summary>
    [Fact]
    public async Task AuditFlagsOnlyDeclarationsTheProofRelieson()
    {
        var src = await File.ReadAllTextAsync(Spec("BoundedRetry/BoundedRetryFreeRetry.dfy"));
        var r = await DafnyProgram.AuditAsync(src, "BoundedRetryFreeRetry.dfy");
        Assert.True(r.IsSuccess, r.Message);

        Assert.Contains(r.Value.Assumptions, a => a.Declaration == "Attempt");
        Assert.DoesNotContain(r.Value.Assumptions, a => a.Declaration == "NeedsClarification");
    }

    /// <summary>
    /// The whole point, end to end: verified Dafny, translated to Python, executed against a real
    /// hand-written module across the extern boundary.
    ///
    /// This needs only an interpreter and the Dafny runtime that translation emits alongside the
    /// code — no Strands, no venv — so it runs anywhere Python is on PATH.
    /// </summary>
    [Fact]
    public async Task GeneratedPythonRunsAgainstTheRealModule()
    {
        var python = FindPython();
        Assert.True(python is not null,
            "no Python interpreter found; looked in the repo venv and on PATH");

        var src = await File.ReadAllTextAsync(Spec("BoundedRetry/BoundedRetryExtern.dfy"));
        var r = await DafnyProgram.TranslateToPythonAsync(src, "BoundedRetryExtern.dfy");
        Assert.True(r.IsSuccess, r.Message);

        var dir = Path.Combine(Path.GetTempPath(), "anchor-roundtrip", Path.GetRandomFileName());
        try
        {
            foreach (var (file, content) in r.Value.Files)
            {
                var path = Path.Combine(dir, file);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                await File.WriteAllTextAsync(path, content);
            }

            // Replace Dafny's empty placeholder with the real implementation.
            File.Copy(Spec("BoundedRetry/anchor_model.py"), Path.Combine(dir, "anchor_model.py"), overwrite: true);

            await File.WriteAllTextAsync(Path.Combine(dir, "driver.py"),
                """
                import module_
                outcome, spent = module_.default__.RunTask(10, 3)
                assert spent <= 10, f"budget violated at runtime: {spent}"
                print(f"OK spent={spent}")
                """);

            var info = new System.Diagnostics.ProcessStartInfo(python!)
            {
                WorkingDirectory = dir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            info.ArgumentList.Add("driver.py");

            using var process = System.Diagnostics.Process.Start(info)!;
            var stdout = await process.StandardOutput.ReadToEndAsync();
            var stderr = await process.StandardError.ReadToEndAsync();
            await process.WaitForExitAsync();

            Assert.True(process.ExitCode == 0, $"python exited {process.ExitCode}\n{stdout}\n{stderr}");
            Assert.Contains("OK spent=", stdout);

            // The model succeeds on its third attempt at cost 2 each, so the workflow spends 6 of 10.
            Assert.Contains("OK spent=6", stdout);
        }
        finally
        {
            try { Directory.Delete(dir, true); } catch (IOException) { /* scratch */ }
        }
    }

    /// <summary>
    /// Any interpreter on PATH. Deliberately not the repo venv: the generated code needs only the
    /// Dafny runtime emitted beside it, and reaching for the venv would imply a Strands dependency
    /// this round-trip does not have.
    /// </summary>
    static string? FindPython()
    {
        var names = OperatingSystem.IsWindows() ? ["python.exe"] : new[] { "python3", "python" };
        var candidates = new List<string>();

        // The repo venv first, when there is one: an interpreter known to work. Any Python does —
        // the generated code needs only the Dafny runtime emitted beside it, so this is not a
        // Strands dependency, just the one we can be sure exists locally.
        var dir = new DirectoryInfo(AssemblyLocation);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "Anchor.sln")))
        {
            dir = dir.Parent;
        }
        if (dir is not null)
        {
            var bin = Path.Combine(dir.FullName, "python", OperatingSystem.IsWindows() ? "Scripts" : "bin");
            candidates.AddRange(names.Select(n => Path.Combine(bin, n)));
        }

        candidates.AddRange((Environment.GetEnvironmentVariable("PATH") ?? "")
            .Split(Path.PathSeparator)
            .Where(d => !string.IsNullOrWhiteSpace(d))
            .SelectMany(d => names.Select(n => Path.Combine(d, n))));

        return candidates.Where(File.Exists).FirstOrDefault(CanRunCode);
    }

    /// <summary>
    /// Existing on disk proves nothing, and neither does answering <c>--version</c>. Windows ships
    /// an App Execution Alias at WindowsApps\python.exe that File.Exists reports happily and which
    /// only prints "Python was not found"; MSYS2's python answers --version but then cannot find its
    /// own stdlib when launched from a Windows process. Require it to actually execute something.
    /// </summary>
    static bool CanRunCode(string exe)
    {
        try
        {
            var info = new System.Diagnostics.ProcessStartInfo(exe)
            {
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            info.ArgumentList.Add("-c");
            info.ArgumentList.Add("print('anchor')");

            using var probe = System.Diagnostics.Process.Start(info);
            if (probe is null)
            {
                return false;
            }
            var output = probe.StandardOutput.ReadToEnd();
            probe.WaitForExit(10_000);
            return probe.HasExited && probe.ExitCode == 0 && output.Contains("anchor");
        }
        catch (Exception)
        {
            return false;
        }
    }

    #endregion
}
