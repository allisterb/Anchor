namespace Anchor.Tests.MCPServer;

using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

using Anchor.MCPServer;

/// <summary>
/// The smoke tier: TLC as a random walk, for models too big to exhaust.
/// </summary>
/// <remarks>
/// <para>
/// THE POLARITY IS INVERTED HERE and these tests exist to keep it that way. The usual smoke test
/// gives a sound NEGATIVE — find a counterexample and the thing is broken, find none and you have
/// learnt nothing. Anchor already reads TLC backwards: a violation is the GOOD outcome, the witness
/// proving a rule does something. So a random walk gives a sound POSITIVE, and its silence means
/// nothing at all.
/// </para>
/// <para>
/// Which makes exactly one mistake catastrophic: reporting VACUOUS, REDUNDANT or DEAD from a smoke
/// run. Each is a claim of ABSENCE, none is established by a random walk, and each of them tells
/// someone to delete a rule. <see cref="SmokeNeverClaimsARuleIsInert"/> is the test that matters.
/// </para>
/// </remarks>
public class SmokeTierTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// THE ONE THAT MATTERS. <c>dead_forbid.dw</c> has a forbid that exhaustive search proves DEAD.
    /// A smoke run must NOT say so — it must say it does not know.
    /// </summary>
    [PolicyCheck]
    public async Task SmokeNeverClaimsARuleIsInert()
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var policy = Path.Combine("tests", "policies", "dead_forbid.dw");

        // Exhaustive first, to establish that there really is an inert rule here to mis-report.
        var exhaustive = await tools.CheckPolicyAsync(policy);
        Assert.True(exhaustive.Answered, exhaustive.Error);
        Assert.Equal("DEAD", Assert.Single(exhaustive.Inert).Verdict);

        var smoke = await tools.CheckPolicyAsync(policy, smoke: 1000);
        Assert.True(smoke.Answered, smoke.Error);

        // Not one of the three absence verdicts, anywhere in the output.
        Assert.Empty(smoke.Inert);
        Assert.DoesNotContain("DEAD", smoke.Output);
        Assert.DoesNotContain("VACUOUS", smoke.Output);
        Assert.DoesNotContain("REDUNDANT", smoke.Output);

        // It is reported as unsettled, and said to be not a verdict.
        var unsettled = Assert.Single(smoke.Unsettled);
        Assert.Equal("forbid", unsettled.Effect);
        Assert.Equal(2, unsettled.Rule);
        Assert.Contains("not a verdict", smoke.Output);
    }

    /// <summary>
    /// The positive half is sound, so a rule smoke calls live must be one exhaustive calls live.
    /// A witness is a witness however it was reached.
    /// </summary>
    [PolicyCheck]
    public async Task WhatSmokeCallsLiveExhaustiveAlsoCallsLive()
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var policy = Path.Combine("tests", "policies", "dead_forbid.dw");

        var smoke = await tools.CheckPolicyAsync(policy, smoke: 1000);
        var exhaustive = await tools.CheckPolicyAsync(policy);

        Assert.True(smoke.Answered, smoke.Error);
        Assert.True(exhaustive.Answered, exhaustive.Error);

        var liveUnderSmoke = smoke.Findings.Where(f => f.Verdict == "live").Select(f => f.Rule).ToHashSet();
        var liveUnderExhaustive = exhaustive.Findings.Where(f => f.Verdict == "live").Select(f => f.Rule).ToHashSet();

        Assert.NotEmpty(liveUnderSmoke);
        Assert.Subset(liveUnderExhaustive, liveUnderSmoke);
    }

    /// <summary>
    /// The tier is named in the output. A smoke verdict read as an exhaustive one is the whole
    /// hazard, so "which search produced this" may not be implicit.
    /// </summary>
    [PolicyCheck]
    public async Task TheOutputSaysItWasNotExhaustive()
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var smoke = await tools.CheckPolicyAsync(
            Path.Combine("tests", "policies", "dead_forbid.dw"), smoke: 250);

        Assert.True(smoke.Answered, smoke.Error);
        Assert.Contains("SMOKE", smoke.Output);
        Assert.Contains("not exhaustive", smoke.Output);
        Assert.Contains("250", smoke.Output);
    }

    /// <summary>
    /// Without <c>smoke</c> nothing changes. The tier is opt-in, and the default path is the one
    /// every other test in the repo relies on.
    /// </summary>
    [PolicyCheck]
    public async Task TheDefaultPathIsUntouched()
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var r = await tools.CheckPolicyAsync(Path.Combine("tests", "policies", "dead_forbid.dw"));

        Assert.True(r.Answered, r.Error);
        Assert.DoesNotContain("SMOKE", r.Output);
        Assert.Empty(r.Unsettled);
        Assert.Equal("DEAD", Assert.Single(r.Inert).Verdict);
    }

    #endregion

    #region Fields

    static readonly string Repo = PythonProcess.FindRoot().IsSuccess
        ? PythonProcess.FindRoot().Value : Directory.GetCurrentDirectory();

    #endregion
}
