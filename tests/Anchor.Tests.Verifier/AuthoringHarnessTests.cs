namespace Anchor.Tests.TLAPlus;

/// <summary>
/// What the agent WRITES, and the gates on each of them: a drafted property module, the plain-
/// English statement of what it forbids, a clarifying question about an ambiguous request, and an
/// unattended report over a whole directory. Every one of these can be produced fluently and be
/// worthless, so every one of them is gated here.
/// </summary>
/// <remarks>
/// <para>
/// One of six classes the harness tests are split across. <b>xunit parallelises across
/// collections, and a class with no <c>[Collection]</c> attribute is its own collection</b> — so
/// tests in one class run strictly one after another, and the suite's wall clock is the slowest
/// single class. Measured: as one class these took 507s serially while seven cores idled. The
/// split is balanced by measured duration, not by count, and the floor is the longest single test.
/// </para>
/// <para>
/// This class holds 87s of the 508s. Its slowest test is
/// <c>ADraftedPropertyIsKeptOnlyIfItCouldHaveFailed</c>, at 38s.
/// </para>
///
/// See <see cref="PythonHarnessAttribute"/> for why any of these may report as skipped.
/// </remarks>
public class AuthoringHarnessTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// Drafting a property module, and the gate that makes it safe: a draft is kept only if it
    /// <b>could have failed</b>.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Drafting is a convenience; refusing to keep one that says nothing is the feature. The
    /// most-reported pathology in agentic verification is a model asked to produce both an artifact
    /// and its specification discovering that a trivial specification is the cheapest way to pass —
    /// and the failure mode is a property that is perfectly, uselessly <i>true</i>. Mutation is the
    /// only mechanical defence: break the policy and see whether the property notices.
    /// </para>
    /// <para>
    /// The negative case is the one that matters, and it is asserted three ways — the draft is
    /// rejected, it is rejected <i>for ranging over nothing that could break it</i>, and nothing is
    /// written to disk. A rejected draft must also not clobber a module somebody wrote by hand,
    /// which is the realistic way this feature would do damage.
    /// </para>
    /// <para>
    /// <b>There are two gates, and the harness carries a fixture each one lets through.</b> Reading
    /// the module catches a claim nothing it ranges over can break, in milliseconds. Mutation
    /// catches a tautology about the <i>decision</i> — <c>Grants(r) \/ ~Grants(r)</c> — which
    /// reading cannot see, because the explainer deliberately does not evaluate the authorization
    /// semantics. A change that collapsed the two into one would pass one fixture and fail the
    /// other, which is the point of keeping both.
    /// </para>
    /// </remarks>
    [PythonHarness("property_authoring.py", "strands")]
    public async Task ADraftedPropertyIsKeptOnlyIfItCouldHaveFailed()
    {
        var run = await PythonHarness.RunAsync("tests/strands/property_authoring.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("a true-but-empty property is rejected", run.Output);
        Assert.Contains("it was rejected for ranging over nothing that could break it", run.Output);
        Assert.Contains("and NOTHING was written", run.Output);
        Assert.Contains("a tautology about the decision is rejected by MUTATION", run.Output);
        Assert.Contains("and the existing module is restored, not clobbered", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// The unattended directory check: every policy found by globbing, every <c>.tla</c> paired
    /// with the policy its header names, and a directory with <b>no</b> stated intentions told
    /// plainly that its clean report means much less.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The orchestration is what is pinned here, not the checks — those have their own tests. What
    /// would rot silently is the honesty: <c>auto</c> over policies with no <c>.tla</c> beside them
    /// produces a report that looks exactly like a pass, and the only thing between that and a
    /// false sense of security is a paragraph saying which questions were never asked.
    /// </para>
    /// <para>
    /// Also pinned: the headline must not be a vacuous truth. With zero stated intentions, "every
    /// stated intention holds" is true and says nothing — which is the precise failure this whole
    /// project exists to catch, and would be an embarrassing one to ship in its own report.
    /// </para>
    /// </remarks>
    [PythonHarness("auto_directory.py", "strands")]
    public async Task AutoFindsEveryPolicyAndSaysWhatItDidNotCheck()
    {
        var run = await PythonHarness.RunAsync("tests/strands/auto_directory.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("a module naming no policy is reported, not dropped", run.Output);
        Assert.Contains("BUT the report says no intentions were stated", run.Output);
        Assert.Contains("and does not claim every intention holds", run.Output);
        Assert.Contains("a broken intention is listed first", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// Ambiguity reporting: a request that admits more than one policy is raised <b>only when the
    /// readings actually decide something differently</b>.
    /// </summary>
    /// <remarks>
    /// <para>
    /// A verifier answers questions about a policy that exists; it cannot say the <i>request</i>
    /// was ambiguous, because by then a reading has already been chosen — silently, by whatever
    /// wrote the policy. That gap is what this closes, and the competing readings are compared
    /// against each other rather than merely listed.
    /// </para>
    /// <para>
    /// <b>The negative case is the one that keeps it honest.</b> A model can always manufacture a
    /// distinction, and an assistant that asks a clarifying question every time trains people to
    /// click past it. Two readings that decide every session alike must not reach a person however
    /// different their text — and "I could not check that one" must not read as "they agree".
    /// </para>
    /// </remarks>
    [PythonHarness("clarify_readings.py", "strands")]
    public async Task AmbiguityIsVerifiedBeforeItIsRaised()
    {
        var run = await PythonHarness.RunAsync("tests/strands/clarify_readings.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("and it comes with a session, not just a verdict", run.Output);
        Assert.Contains("readings that agree on every session are NOT material", run.Output);
        Assert.Contains("an unusable reading is excluded from a no-difference claim", run.Output);
        Assert.Contains("no readings is not the same as no ambiguity", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// The plain-English explainer: what a property module <b>forbids</b>, said before anything is
    /// checked.
    /// </summary>
    /// <remarks>
    /// <para>
    /// This is the checkpoint at the one boundary where the literature says autonomy fails — the
    /// formulation of the property itself. Everything downstream of a property is mechanical and
    /// checkable; everything upstream is a person saying what they meant. A property that says
    /// something <i>other</i> than what its author meant is checked just as rigorously, and passes
    /// just as convincingly.
    /// </para>
    /// <para>
    /// <b>Nothing here runs TLC</b>, which is the feature rather than a shortcut: a checkpoint that
    /// costs minutes is a checkpoint people skip. What would rot silently is the <i>sense</i> of the
    /// generated English — <c>~Grants(req)</c> glossed as "the policy GRANTS it" reads perfectly and
    /// is exactly backwards — so the harness asserts the direction of the rendering per shape, in
    /// both polarities, rather than the shape of the output.
    /// </para>
    /// <para>
    /// The counting is the other half. <c>A =&gt; B</c> tests nothing in any state where <c>A</c> is
    /// false, so "applies to 3 of the 6" is the size of the experiment, and <i>none of them</i> is a
    /// claim that will pass having examined nothing.
    /// </para>
    /// </remarks>
    [PythonHarness("property_explainer.py", "strands")]
    public async Task WhatAPropertyForbidsIsStatedBeforeItIsChecked()
    {
        var run = await PythonHarness.RunAsync("tests/strands/property_explainer.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("a claim that the policy must ALLOW forbids a refusal", run.Output);
        Assert.Contains("a claim whose condition no state satisfies is reported as vacuous", run.Output);
        Assert.Contains("a tautology about the DECISION is not caught by reading alone", run.Output);
        Assert.Contains("the policy's decision is UNKNOWN, never guessed", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// The authoring pipeline as the Strands <c>Graph</c> that runs it: one agent drafts, a
    /// different one reports, and the two gates between them are criteria in code.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The load-bearing assertion is the last one. <c>tests/strands/anchor_workflow.py</c> chose
    /// this shape by checking four properties against four wirings — but it chose it over graphs
    /// built from scripted stand-ins. This runs the same translation over the graph
    /// <c>pipeline.build</c> actually returns and re-proves <c>AlwaysReports</c> on it, so the
    /// shape that was checked and the object that runs cannot drift apart.
    /// </para>
    /// </remarks>
    [PythonHarness("pipeline_run.py", "strands")]
    public async Task TheAuthoringPipelineRunsAsTheGraphThatWasChecked()
    {
        var run = await PythonHarness.RunAsync("tests/strands/pipeline_run.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("all checks passed", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);

        // A rejected draft costs nothing downstream — no TLC, no second model call — and still
        // reports. Both halves, because either alone would be the wrong behaviour.
        Assert.Contains("ran 4/7: describe, draft, preflight, report", run.Output);
        Assert.Contains("ok    the answerer was not invoked", run.Output);
        Assert.Contains("ok    report ran anyway", run.Output);
        Assert.Contains("ok    findings.md says nothing was verified", run.Output);

        // An accepted draft goes the whole way, and the answerer sees the verdicts rather than the
        // drafter's module — the separation as it actually lands, not as it was intended.
        Assert.Contains("ran 7/7: describe, draft, preflight, score, check, answer, report", run.Output);
        Assert.Contains("ok    the answerer did NOT see the draft", run.Output);

        // And the claim the whole graph exercise was for.
        Assert.Contains("ok    AlwaysReports HOLDS on the graph that actually runs", run.Output);
    }

    #endregion
}
