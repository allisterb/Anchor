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
/// This class holds 93s of the 508s. Its slowest test is
/// <c>RepairLoopFeedsTheCheckersObjectionBackAndIsBounded</c>, at 93s.
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

    #endregion
}
