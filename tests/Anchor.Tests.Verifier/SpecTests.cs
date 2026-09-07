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

    /// <summary>
    /// The budget is never exceeded and the task always ends — for every behaviour of a model that
    /// is free to fail forever and charge the maximum every time.
    /// </summary>
    [Fact]
    public async Task BoundedRetryVerifies()
    {
        var run = await CheckAsync("BoundedRetry");
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
        var run = await CheckAsync("Bug1_Overshoot");
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
        var run = await CheckAsync("Bug2_FreeRetry");
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
        var run = await CheckAsync("SharedBudget");
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
        var run = await CheckAsync("Bug3_CheckThenReserve");
        Assert.False(run.Verified);
        Assert.Contains(run.Errors, e => e.Code == TLCCodes.InvariantViolated);
        Assert.Contains("BudgetSafe", string.Join("\n", run.Errors.Select(e => e.Text)));

        // The race window itself: both agents past the check, neither yet reserved. Each is acting
        // on an affordability decision that was true when taken and is about to stop being true.
        Assert.Contains(run.Trace, s =>
            s.Text.Contains("a1 :> \"checked\"") && s.Text.Contains("a2 :> \"checked\""));
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
        var run = await VerifyAsync("BoundedRetry.dfy");
        Assert.True(run.Verified, run.Output);
    }

    /// <summary>
    /// The free-retry bug again, in the other tool. TLC reports it as a lasso; Dafny rejects the
    /// termination measure. Both are the same claim — that every pass consumes something.
    /// </summary>
    [Fact]
    public async Task FreeRetryFailsTerminationButNotSafety()
    {
        var run = await VerifyAsync("BoundedRetryFreeRetry.dfy");
        Assert.False(run.Verified);

        // Termination is what fails.
        Assert.Contains("decreases expression might not decrease", run.Output);

        // And only termination. The budget postconditions still hold, because a round that spends
        // nothing cannot overspend — which is precisely why an invariant-only checker misses this.
        Assert.DoesNotContain("postcondition", run.Output);
        Assert.DoesNotContain("invariant", run.Output);
    }

    #endregion
}
