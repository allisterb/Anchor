namespace Anchor.Tests.TLAPlus;

/// <summary>
/// The derived checks — the questions answerable without knowing what a policy is FOR. Is a permit
/// reachable, is a rule load-bearing, which condition term makes an inert rule inert, and can a
/// reader re-run the model the verdict came from.
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
/// <c>BlameNamesTheTermsThatMakeARuleInert</c>, at 23s.
/// </para>
///
/// See <see cref="PythonHarnessAttribute"/> for why any of these may report as skipped.
/// </remarks>
public class VacuityHarnessTests : TestsRuntime
{
    #region Methods

    /// <summary>
    /// Blame minimisation: <b>which</b> part of an inert rule made it inert. A verdict sends a
    /// reader back to re-read their own condition; a minimal core is an instruction.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Unsat-core minimisation, one level of decomposition below the rule: drop conjuncts and
    /// re-ask, keeping only those whose presence still kills it. Greedy, so the result is
    /// <i>1-minimal</i> — removing any single term from the answer revives the rule — which is
    /// what N runs can honestly claim, as against 2^N for globally smallest.
    /// </para>
    /// <para>
    /// <b>Both halves of this fixture are load-bearing.</b> The permit's answer is a PAIR: neither
    /// origin term is unsatisfiable alone, so a per-term check finds nothing and only a core
    /// catches the contradiction — while the irrelevant port term must be dropped. The forbid is
    /// dead for a reason that is not in its condition at all, which is why the search asks
    /// "inert with NO condition?" first; skipping that question yields a confident answer pointing
    /// at the wrong term.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task BlameNamesTheTermsThatMakeARuleInert()
    {
        var run = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/vacuous_two_terms.dw");

        Assert.True(run.ExitCode == 0, run.Output);

        // The contradictory pair, and NOT the satisfiable term alongside them.
        Assert.Contains("because: input.origin == nowhere && input.origin == local", run.Output);
        Assert.DoesNotContain("because: input.port == 22", run.Output);

        // The forbid's deadness is structural, so the condition must not be blamed for it.
        Assert.Contains("the condition is not why", run.Output);
        Assert.DoesNotContain("because: input.origin == external", run.Output);

        // --no-blame turns the whole search off, which is the point of having the flag.
        var quiet = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/vacuous_two_terms.dw", "--no-blame");

        Assert.True(quiet.ExitCode == 0, quiet.Output);
        Assert.Contains("VACUOUS", quiet.Output);
        Assert.DoesNotContain("because:", quiet.Output);
        Assert.DoesNotContain("the condition is not why", quiet.Output);
    }

    /// <summary>
    /// Beyond vacuity: is each rule <b>load-bearing</b> — does deleting it change any verdict?
    /// One question, and it covers a dead <c>forbid</c> and a redundant <c>permit</c> alike.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The three verdicts are deliberately not collapsed, because they are different findings.
    /// <b>VACUOUS</b> means the permit never fires at all — whatever it was meant to allow is
    /// unreachable, which is a bug rather than untidiness. <b>REDUNDANT</b> means it fires
    /// perfectly well and another permit always would too. <b>DEAD</b> means the forbid never
    /// denies anything the rest of the set would have allowed. Vacuous implies redundant; the
    /// converse does not hold, and <c>redundant_permit.dw</c> is the case that proves the
    /// checker tells them apart rather than reporting the weaker answer for both.
    /// </para>
    /// <para>
    /// Mutation-checked where it would silently over-report: making the "policy set without this
    /// rule" a no-op turns every rule redundant, and this test's <c>live</c> assertion catches it.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task LoadBearingCheckSeparatesDeadRedundantAndLive()
    {
        // A forbid on an action no permit covers. It reads like a control and denies nothing,
        // because default-deny had already shut that door.
        var forbid = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/dead_forbid.dw");

        Assert.True(forbid.ExitCode == 0, forbid.Output);
        Assert.Matches(@"permit #1\s+action == Trade\s+live", forbid.Output);
        Assert.Matches(@"forbid #2\s+action == Approve\s+DEAD", forbid.Output);

        // A gated permit sitting under an unconditional one. It fires — so it is NOT vacuous —
        // and it still decides nothing.
        var redundant = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/redundant_permit.dw");

        Assert.True(redundant.ExitCode == 0, redundant.Output);
        Assert.Matches(@"permit #2\s+action == Trade\s+REDUNDANT", redundant.Output);
        // Targets the verdict column, not the prose. A bare DoesNotContain matched the legend
        // that explains the word, which is a different thing from reporting it.
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", redundant.Output);

        // And the distinction survives: a permit a forbid always overrides is still VACUOUS,
        // not merely redundant.
        var vacuous = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/overridden_permit.dw");

        Assert.True(vacuous.ExitCode == 0, vacuous.Output);
        Assert.Matches(@"permit #1\s+action == Trade\s+VACUOUS", vacuous.Output);
    }

    /// <summary>
    /// The generic checker, run on the AgentCore documentation's own trading example, reproduces
    /// the finding <c>TemporalPolicy.tla</c> reaches by hand — from the policy text, with nobody
    /// translating anything.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Two models built independently agreeing on one result is worth more than either alone.
    /// <c>TemporalPolicy.tla</c> carries a hand-written <c>PermitFires</c> and a hand-written
    /// <c>Policies.tla</c>; <c>Vacuity.tla</c> carries neither, taking its policies from parsed
    /// <c>.dw</c> text and its decision from the corpus-validated evaluator. They share no code
    /// on the path that matters, so this is a real cross-check rather than a restatement.
    /// </para>
    /// <para>
    /// It also exercises the two constructs the simpler cases do not: the first-order join
    /// (<c>input.stock: context.input.stock</c> — "an approval for THIS stock", which
    /// propositional temporal logic cannot express) and an output-field bind
    /// (<c>output.approved: true</c>).
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task VacuityCheckerReproducesTheHandWrittenSpecsFinding()
    {
        var live = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading.dw");

        Assert.True(live.ExitCode == 0, live.Output);
        Assert.Matches(@"action == SellShares\s+live\s+witness: ApproveSale -> SellShares", live.Output);

        // The same file with approvals forbidden instead of permitted. The SellShares permit is
        // untouched — and now grants nothing, because a denied approval is recorded as an `error`
        // and the `::response` it waits for is never written.
        var vacuous = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading_forbidden.dw");

        Assert.True(vacuous.ExitCode == 0, vacuous.Output);
        Assert.Matches(@"action == SellShares\s+VACUOUS", vacuous.Output);
    }

    /// <summary>
    /// The vacuity checker over arbitrary Dogwood policy files: can this permit ever actually
    /// grant anything? Pinned on two policies that differ by <b>one word</b> and get opposite
    /// answers, and on the second shape of vacuity, which a satisfiability check cannot see.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Nothing here is hand-modelled. The <c>.dw</c> text is parsed by the same parser that agrees
    /// with the reference implementation on 911 corpus pairs, and evaluated by the same
    /// <c>DogwoodSemantics!Decide</c>. That is what makes this "hand us a policy and we will
    /// model-check it" rather than "here is a policy we modelled".
    /// </para>
    /// <para>
    /// The VACUOUS verdict is the one that must never be wrong, because it is the silent
    /// direction — a permit reported inert when it is merely deep would send someone to delete a
    /// working control. It is falsification-tested: adding a permit for the approval the gate
    /// waits on flips the same file to live, so the verdict is attributable to the denied
    /// approval rather than to the model being unable to reach a response at all.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task VacuityCheckerSeparatesPoliciesOneWordApart()
    {
        // Gated on a COMPLETED approval. No permit covers the approval, so it is denied, so it is
        // recorded as `error` rather than `response`, so this gate can never open.
        var vacuous = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/approval_gate_response.dw");

        Assert.True(vacuous.ExitCode == 0, vacuous.Output);
        Assert.Matches(@"action == Trade\s+VACUOUS", vacuous.Output);

        // The same policy with `response` changed to `request` — and a witness session, because a
        // request event is recorded for every attempt, permitted or not.
        var live = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/approval_gate_request.dw");

        Assert.True(live.ExitCode == 0, live.Output);
        Assert.Matches(@"action == Trade\s+live\s+witness: Approve -> Trade", live.Output);

        // Matched but never granted: forbid overrides permit. Distinguishing this from the case
        // above is the whole reason the spec tracks GRANTED rather than matched.
        var overridden = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/overridden_permit.dw");

        Assert.True(overridden.ExitCode == 0, overridden.Output);
        Assert.Matches(@"action == Trade\s+VACUOUS", overridden.Output);
    }

    /// <summary>
    /// <c>--keep</c> preserves the model a verdict came from, for every question the checker
    /// answers — not just the comparison it was first written for.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>A verdict from a model checker is only as good as the model.</b> These were written to a
    /// temp directory and deleted on the way out, so nobody could examine the thing the answer
    /// came from — an awkward position for a project whose claim is that its answers are
    /// checkable.
    /// </para>
    /// <para>
    /// The per-rule case is the one that needs asserting rather than eyeballing: each rule runs
    /// under a different <c>Target</c>, so a single kept config would silently describe whichever
    /// rule happened to be checked last. This pins one config and one output PER RULE, and pins
    /// that the <c>Target</c> values actually differ.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task KeptArtifactsCoverEveryRuleNotJustTheLast()
    {
        var dir = Path.Combine(Path.GetTempPath(), "anchor-keep-" + Guid.NewGuid().ToString("N"));
        try
        {
            // dead_forbid.dw is one permit and one forbid, so the permit draws both questions
            // (NeverMatters and NeverFires) and the forbid draws only the first.
            var run = await PythonHarness.RunAsync(
                "src/checker/properties.py", "tests/policies/dead_forbid.dw", "--keep", dir);

            Assert.True(run.ExitCode == 0, run.Output);

            foreach (var name in new[] { "PolicyUnderTest.tla", "Vacuity.tla",
                                         "DogwoodSemantics.tla", "README.md",
                                         "rule-1-NeverMatters.cfg", "rule-1-NeverMatters.tlc.txt",
                                         "rule-1-NeverFires.cfg",
                                         "rule-2-NeverMatters.cfg", "rule-2-NeverMatters.tlc.txt" })
            {
                Assert.True(File.Exists(Path.Combine(dir, name)), $"missing {name}");
            }

            // The forbid is not a permit, so it is never asked whether it FIRES.
            Assert.False(File.Exists(Path.Combine(dir, "rule-2-NeverFires.cfg")));

            // Each rule's config targets that rule. Equal targets would mean the kept configs are
            // copies of one run wearing different names.
            Assert.Contains("Target = 1", await File.ReadAllTextAsync(Path.Combine(dir, "rule-1-NeverMatters.cfg")));
            Assert.Contains("Target = 2", await File.ReadAllTextAsync(Path.Combine(dir, "rule-2-NeverMatters.cfg")));

            // The README must name a jar that exists, or the reproduction instructions are a
            // promise that cannot be kept. It said `tla2tools.jar` once; the file is versioned.
            var readme = await File.ReadAllTextAsync(Path.Combine(dir, "README.md"));
            var jar = readme.Split('\n').First(l => l.Contains("tlc2.TLC"))
                            .Split("-cp ")[1].Split(" tlc2.TLC")[0];
            Assert.True(File.Exists(jar), $"README names a jar that does not exist: {jar}");
        }
        finally
        {
            if (Directory.Exists(dir)) Directory.Delete(dir, recursive: true);
        }
    }

    #endregion
}
