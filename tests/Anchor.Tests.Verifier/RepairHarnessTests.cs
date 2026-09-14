namespace Anchor.Tests.TLAPlus;

/// <summary>
/// The bounded repair loop — propose, check, feed the objection back, repeat — and the transcript
/// it leaves behind.
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
/// This class measured <b>157s</b> in the last full run, its slowest test being
/// <c>RepairLoopFeedsTheCheckersObjectionBackAndIsBounded</c> at 157s. Those are wall clock UNDER
/// CONTENTION — five other classes are running — so they are 2-3x what the same test
/// takes alone, and they predate the checker memo. The 508s split above is older still.
/// </para>
///
/// See <see cref="PythonHarnessAttribute"/> for why any of these may report as skipped.
/// </remarks>
public class RepairHarnessTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// The bounded repair loop — propose, check, feed the objection back, revise — driven by a
    /// scripted proposer so the mechanics are verified without a model.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>The loop is code and the model only proposes.</b> That split is what stops the pathology
    /// the literature reports most often in repair loops: when a property is hard to satisfy, a
    /// model weakens the property. Here the acceptance criteria are arguments evaluated after the
    /// model has spoken, and the harness proves it — the same candidate is rejected under
    /// <c>no_widening</c> and accepted without it, which no amount of prompting could change.
    /// </para>
    /// <para>
    /// It also pins the thing a green loop can silently lack: that the objection actually
    /// <i>reaches</i> the next round. A loop that checks and then discards the complaint would
    /// pass every other assertion, because the scripted second answer is right regardless.
    /// </para>
    /// </remarks>
    [PythonHarness("repair_loop.py", "strands")]
    public async Task RepairLoopFeedsTheCheckersObjectionBackAndIsBounded()
    {
        var run = await PythonHarness.RunAsync("tests/strands/repair_loop.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("the complaint names the DEAD forbid", run.Output);
        Assert.Contains("round 2 was given the objection", run.Output);
        Assert.Contains("and runs out AT the bound, not past it", run.Output);
        Assert.Contains("a widening candidate is rejected when --no-widening is set", run.Output);
        // The property gate, which had no coverage and was broken the whole time it had none.
        Assert.Contains("a candidate that satisfies the property draws no complaint", run.Output);
        Assert.Contains("a candidate that breaks it is rejected", run.Output);

        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// Transcript rendering: a saved exchange must show every tool call with its arguments and
    /// its reply — and must <b>say so</b> when an answer rested on no tool calls at all.
    /// </summary>
    /// <remarks>
    /// A transcript exists so somebody can check the agent's prose against what the tools actually
    /// returned, which only works if the rendering is faithful. The load-bearing case is the last:
    /// a model can produce a confident paragraph about a policy it never looked at, and in a saved
    /// log that is indistinguishable from a checked verdict unless the absence is stated.
    /// </remarks>
    [PythonHarness("transcript_render.py", "strands")]
    public async Task TranscriptsShowTheToolCallsOrSayThereWereNone()
    {
        var run = await PythonHarness.RunAsync("tests/strands/transcript_render.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("its ARGUMENTS are shown", run.Output);
        Assert.Contains("an answer with no tool calls is flagged as such", run.Output);
        Assert.Contains("an unmodelled result block is named rather than dropped", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);
    }

    /// <summary>
    /// The memo under every verdict: the same checker answer, never a stale one.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>A cache in a verification tool is a liability unless it is exact.</b> What it buys is
    /// wall clock — about 1.6s of every ~2.0s TLC run is starting a JVM, so the price of a check is
    /// paid per invocation almost regardless of what is being checked, and the pipeline asks the
    /// same question several times per run: the derived questions depend on the <i>policy</i>
    /// alone, so a <c>hitl</c> session of four attempts asks them four times, and a sweep of five
    /// requirements against one policy asks them five times.
    /// </para>
    /// <para>
    /// What it risks is a verdict about a file that has since changed, so the assertions here are
    /// about the <i>answer</i> and never about the speed. Determinism is established rather than
    /// assumed — the same call is made twice with the memo off and the verdicts compared — because
    /// the whole design rests on it and a future sampling or timeout-shaped heuristic would break
    /// it silently.
    /// </para>
    /// <para>
    /// The key is the file's <b>content</b>, not its path: a drafted module is rewritten to the
    /// same path every round, so a path-keyed memo would answer round 2 with round 1's verdict and
    /// report a fixed module as still broken with no sign anything went wrong. And <c>--keep</c> is
    /// never cached, because that flag is what makes the checker write the model and the raw TLC
    /// output to a directory the caller reads afterwards — <c>audit.py</c> passes it.
    /// </para>
    /// </remarks>
    [PythonHarness("checker_memo.py", "strands")]
    public async Task TheCheckerMemoGivesTheSameAnswerAndNeverAStaleOne()
    {
        var run = await PythonHarness.RunAsync("tests/strands/checker_memo.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("all checks passed", run.Output);
        Assert.DoesNotContain("FAIL", run.Output);

        // The assumption the whole design rests on, and the comparison that keeps it honest.
        Assert.Contains("ok    the checker gave the same verdict twice", run.Output);
        Assert.Contains("ok    the memo's answers match the checker's", run.Output);
        // ...against real verdicts. A memo returning "_failed" for everything would satisfy the
        // two assertions above.
        Assert.Contains("ok    the verdicts being compared are real", run.Output);

        // CONTENT, NOT PATHS — the worst and quietest failure this could have.
        Assert.Contains("ok    a changed POLICY at the same path is a different question", run.Output);
        Assert.Contains("ok    an identical rewrite of the module IS reused", run.Output);
        Assert.Contains("ok    ...but a changed module is not", run.Output);

        // A call that writes to disk cannot be answered from memory.
        Assert.Contains("ok    a --keep call is refused a cache key", run.Output);
        Assert.Contains("ok    ...and the directory was written by the second one", run.Output);

        // It holds TLC transcripts, so it is bounded — and it can be switched off.
        Assert.Contains("ok    it never exceeds LIMIT", run.Output);
        Assert.Contains("ok    with ANCHOR_CHECKER_MEMO=0 nothing is reused", run.Output);
    }

    #endregion
}
