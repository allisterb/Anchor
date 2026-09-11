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
/// (requirements/strands/install.cmd) and which CI does not set up. Skipping is visible in the run summary;
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
    /// This closes the largest caveat on <c>specs/policy/TemporalPolicy</c>: that it modelled the
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
    [PythonHarness("dogwood_differential.py",
                   RequiresPath = "ext/dogwood/dogwood-language/tests/passing/temporal_only/corpus")]
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
        Assert.True(int.Parse(m.Groups[1].Value) >= 640,
                    $"only {m.Groups[1].Value} pairs checked\n{run.Output}");
    }

    /// <summary>
    /// Cedar's <c>like</c> is evaluated by TLC, and a field carrying two patterns gets a value
    /// satisfying both — or a refusal, never a guess.
    /// </summary>
    /// <remarks>
    /// <para>
    /// A TLA+ string is a sequence, and TLC's <c>Sequences</c> implementation supports
    /// <c>Len</c>, <c>\o</c> and <c>SubSeq</c> on one. What it does not support is applying a
    /// string as a function — <c>s[1]</c> fails — so <c>LikeMatches</c> reads a character as
    /// <c>SubSeq(s, i, i)</c>. The pattern semantics therefore live in the spec, like every other
    /// operator's, rather than in the harness.
    /// </para>
    /// <para>
    /// The first assertion guards a false <b>VACUOUS</b>, the same species as
    /// <see cref="FieldDomainsComeFromTheLiteralsThePolicyNames"/>: the vacuity checker invents
    /// the values a field can take, so unless it invents one the pattern matches, the guard can
    /// never be true and a working permit is declared inert.
    /// </para>
    /// <para>
    /// The second is the case that needs a value satisfying two patterns at once.
    /// <c>stock like "A*" &amp;&amp; stock like "*L"</c> is satisfied by <c>"AAPL"</c>, but the
    /// per-pattern witnesses are <c>"A"</c> and <c>"L"</c> and neither satisfies the other. Since
    /// TLC judges the real pattern, an invented candidate can never make a policy falsely live —
    /// only fail to be found — so the checker constructs one and this stays <c>live</c>.
    /// </para>
    /// <para>
    /// The third is where that search comes up empty. Nothing starts with both A and B, so
    /// VACUOUS is the <i>correct</i> verdict and the checker still refuses: at that point "no such
    /// string exists" is indistinguishable from "the search was not clever enough", and reporting
    /// VACUOUS on a hunch tells someone to delete a rule.
    /// </para>
    /// </remarks>
    [PythonHarness("vacuity.py")]
    public async Task LikePatternsAreEvaluatedByTheModel()
    {
        var one = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/like_prefix.dw");

        Assert.True(one.ExitCode == 0, one.Output);
        Assert.Matches(@"permit #1\s+action == SellShares\s+live", one.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", one.Output);

        // Two patterns, jointly satisfiable: a witness is constructed and the permit stays live.
        var two = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/like_two_patterns.dw");

        Assert.True(two.ExitCode == 0, two.Output);
        Assert.Matches(@"permit #1\s+action == SellShares\s+live", two.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", two.Output);

        // Two patterns no string satisfies: refused, and specifically not reported vacuous.
        var none = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/like_impossible.dw");

        Assert.Equal(2, none.ExitCode);
        Assert.Contains("`like` patterns at once", none.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", none.Output);
    }

    /// <summary>
    /// Our reading against Dogwood's own <b>documentation examples</b> — whole policies, rather
    /// than the unit corpus's one-construct-per-case.
    /// </summary>
    /// <remarks>
    /// <para>
    /// A different kind of evidence, and the one that answers "would this work on my policy". The
    /// unit corpus is written to test the engine construct by construct; these are written to show
    /// someone how to use the language, so they are closer to the population a real policy comes
    /// from. The coverage number is therefore the honest one, and it is lower.
    /// </para>
    /// <para>
    /// Two conventions differ from the unit corpus and both would silently misalign every verdict:
    /// the oracle is the CLI's <c>ALLOW</c>/<c>DENY</c> rather than <c>true</c>/<c>false</c>, and
    /// "time point N" counts <b>decisions</b> here where it indexes the whole trace there. The
    /// harness keys on the <c>@N</c> timestamp, which means the same thing in both.
    /// </para>
    /// <para>
    /// Asserted as a floor rather than an exact figure: widening the subset should move it up, and
    /// a drop means something regressed.
    /// </para>
    /// </remarks>
    [PythonHarness("dogwood_examples.py")]
    public async Task OurReadingAgreesWithDogwoodsOwnExamples()
    {
        var run = await PythonHarness.RunAsync("tests/strands/dogwood_examples.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("AGREE", run.Output);
        Assert.DoesNotContain("DISAGREE", run.Output);

        // The attribution check is only worth anything where the verdict does not already force
        // the answer, and most decisions here are single-policy, where it does. If that floor
        // ever reaches zero the check still prints AGREE while proving nothing.
        var attrib = System.Text.RegularExpressions.Regex.Match(
            run.Output, @"attribution checked on (\d+) decisions, of which (\d+)");
        Assert.True(attrib.Success, run.Output);
        Assert.True(int.Parse(attrib.Groups[2].Value) >= 8,
                    $"only {attrib.Groups[2].Value} decisions have an unforced attribution, so the "
                    + $"check is close to vacuous\n{run.Output}");

        // Enough examples to mean something. A silent narrowing — a parser change refusing more
        // than it did — would otherwise still report a hollow success.
        var m = System.Text.RegularExpressions.Regex.Match(run.Output, @"checked\s+(\d+) of (\d+)");
        Assert.True(m.Success, run.Output);
        Assert.True(int.Parse(m.Groups[1].Value) >= 32,
                    $"only {m.Groups[1].Value} examples translated\n{run.Output}");
    }

    /// <summary>
    /// Our semantics against the real Dogwood engine, on traces we construct — specifically ones
    /// containing the <c>error</c> event kind, which appears in <b>zero</b> policies and
    /// <b>zero</b> traces across all 521 corpus cases.
    /// </summary>
    /// <remarks>
    /// The corpus validates a lot, but only over traces Amazon happened to record. `error` is the
    /// kind AgentCore uses for a denied action, and it is what both TemporalPolicy findings rest
    /// on: a permit gated on <c>::response</c> goes vacuous when its dependency is forbidden, and
    /// the same rule written against <c>::request</c> does not. The built binary is a live oracle
    /// and will judge any trace, so those claims are now executed rather than only modelled.
    /// <para>
    /// Skipped unless the binary has been built — it is not in the repo. Mutation-checked: making
    /// our <c>Matches</c> ignore the event kind, or treat <c>error</c> as <c>response</c>, each
    /// turns this red.
    /// </para>
    /// </remarks>
    [PythonHarness("dogwood_replay.py",
                   RequiresExecutable = "ext/dogwood/target/release/dogwood")]
    public async Task DogwoodSemanticsAgreeWithTheEngineOnErrorEvents()
    {
        var run = await PythonHarness.RunAsync("tests/strands/dogwood_replay.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.Contains("agrees with the Dogwood engine on every scenario", run.Output);
        Assert.DoesNotContain("MODEL DISAGREES", run.Output);

        // The finding itself, not just that the scenarios ran: the same denied approval opens a
        // request-gate and not a response-gate.
        Assert.Contains("request-gate, approval DENIED", run.Output);
        Assert.Matches(@"response-gate, approval DENIED\s+@1=DENY, @3=DENY", run.Output);
        Assert.Matches(@"request-gate, approval DENIED\s+@1=DENY, @3=ALLOW", run.Output);
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
    [PythonHarness("vacuity.py")]
    public async Task VacuityCheckerSeparatesPoliciesOneWordApart()
    {
        // Gated on a COMPLETED approval. No permit covers the approval, so it is denied, so it is
        // recorded as `error` rather than `response`, so this gate can never open.
        var vacuous = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/approval_gate_response.dw");

        Assert.True(vacuous.ExitCode == 0, vacuous.Output);
        Assert.Matches(@"action == Trade\s+VACUOUS", vacuous.Output);

        // The same policy with `response` changed to `request` — and a witness session, because a
        // request event is recorded for every attempt, permitted or not.
        var live = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/approval_gate_request.dw");

        Assert.True(live.ExitCode == 0, live.Output);
        Assert.Matches(@"action == Trade\s+live\s+witness: Approve -> Trade", live.Output);

        // Matched but never granted: forbid overrides permit. Distinguishing this from the case
        // above is the whole reason the spec tracks GRANTED rather than matched.
        var overridden = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/overridden_permit.dw");

        Assert.True(overridden.ExitCode == 0, overridden.Output);
        Assert.Matches(@"action == Trade\s+VACUOUS", overridden.Output);
    }

    /// <summary>
    /// The <c>specs/strands/ToolExecutor</c> finding, against a <b>running agent</b> rather than
    /// against a reading of the SDK source.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Every other finding here is checked against something that can disagree — the Dogwood
    /// corpus, the built engine, the real Cedar bindings. That one was backed only by three lines
    /// of quoted dispatch logic, which is weaker evidence than it looked. This runs a real
    /// <c>Agent</c> with a scripted model that emits four tool uses in one turn, so the default
    /// <c>ConcurrentToolExecutor</c> genuinely spawns four tasks, and puts the same hook body
    /// through all three grains the spec models.
    /// </para>
    /// <para>
    /// The concurrency count is the load-bearing observation: a <c>def</c> callback never has more
    /// than <b>one</b> body in flight, so it cannot be interleaved, while the <c>async</c> ones
    /// have four. Without that, a green run would prove only that nothing happened to overlap —
    /// so the probe fails loudly if the batch never overlapped at all.
    /// </para>
    /// </remarks>
    [PythonHarness("tool_hook_probe.py", "strands")]
    public async Task RunningAgentBehavesAsTheToolExecutorSpecPredicts()
    {
        var run = await PythonHarness.RunAsync("tests/strands/tool_hook_probe.py");
        Assert.True(run.ExitCode == 0, run.Output);

        Assert.DoesNotContain("NOT WHAT THE SPEC PREDICTS", run.Output);

        // A synchronous hook cannot be interleaved: one body in flight, and the cap holds.
        Assert.Matches(@"synchronous hook\s+1\s+4\s+1\s+cap holds", run.Output);

        // An await AFTER the write is safe even though four bodies overlap — the counter still
        // serialises. "Async hooks are unsafe" would be too crude, and this is why.
        Assert.Matches(@"suspends AFTER the write\s+4\s+4\s+1\s+cap holds", run.Output);

        // An await BETWEEN read and write loses updates: a cap of one admits four calls, and the
        // counter ends at one. Both of the spec's properties fail, exactly as modelled.
        Assert.Matches(@"BETWEEN read and write\s+4\s+1\s+4\s+CAP EXCEEDED", run.Output);
    }

    /// <summary>
    /// Each field carries its own domain, derived from the literals the policy names — so a policy
    /// reading several fields can be explored, and a field's <em>type</em> is not assumed.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Both halves fix a real limit. One shared domain moved every field together, so a policy
    /// reading two of them had to be refused rather than under-explored — <b>34%</b> of the
    /// parseable corpus. And every output field was modelled as a boolean, so a gate on a string
    /// output could never match and was reported <b>VACUOUS</b>: a working permit declared inert,
    /// which is the one wrong answer this tool must not give. Eight output binds in Dogwood's own
    /// corpus compare against a string.
    /// </para>
    /// <para>
    /// Mutation-checked: ignoring the literals a policy names brings the false VACUOUS straight
    /// back, which is what this test's <c>live</c> assertion catches.
    /// </para>
    /// </remarks>
    [PythonHarness("vacuity.py")]
    public async Task FieldDomainsComeFromTheLiteralsThePolicyNames()
    {
        var strings = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/string_output.dw");

        Assert.True(strings.ExitCode == 0, strings.Output);
        Assert.Matches(@"permit #2\s+action == Read\s+live", strings.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", strings.Output);

        // The docs' trading example reads an input field and an output field, and joins on the
        // input — so it only works if the two move independently.
        var trading = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/docs_trading.dw");

        Assert.True(trading.ExitCode == 0, trading.Output);
        Assert.Matches(@"permit #2\s+action == SellShares\s+live", trading.Output);
    }

    /// <summary>
    /// Policy diff: is there a session two versions of a policy set decide differently? The
    /// question a policy author actually has when editing a set somebody else wrote.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Same mechanism as the load-bearing check — compare two policy sets at every decision
    /// across every session — differing only in where the second set comes from. That is why
    /// there is no separate spec: a duplicated session model would drift, and this repo already
    /// carries <c>dw_to_tla.py --check</c> because copies drift.
    /// </para>
    /// <para>
    /// <b>"No difference" is the answer that must never be wrong</b>, because it tells someone
    /// their edit was safe. It rests on the action vocabulary being the <b>union</b> of both
    /// files: take it from the first alone and an action only the second mentions is never
    /// attempted, so the run reports no difference having never looked. The third case below
    /// pins exactly that, and dropping the union turns it red.
    /// </para>
    /// </remarks>
    [PythonHarness("vacuity.py")]
    public async Task PolicyDiffFindsASessionTheTwoVersionsDecideDifferently()
    {
        // One line apart: approvals permitted, versus forbidden.
        var differs = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/docs_trading.dw",
            "--against", "tests/policies/docs_trading_forbidden.dw");

        Assert.True(differs.ExitCode == 0, differs.Output);
        Assert.Contains("THEY DIFFER", differs.Output);

        // Deleting the rule the checker called REDUNDANT. The two findings check each other:
        // "removing this changes no verdict" and "these files decide identically" are the same
        // claim from opposite ends, so a disagreement would mean one of them is wrong.
        var same = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/redundant_permit.dw",
            "--against", "tests/policies/redundant_permit_minimal.dw");

        Assert.True(same.ExitCode == 0, same.Output);
        Assert.Contains("no difference", same.Output);
        Assert.DoesNotContain("THEY DIFFER", same.Output);

        // The difference is on an action only the SECOND file mentions, so this passes only if
        // the vocabulary spans both.
        var added = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/redundant_permit_minimal.dw",
            "--against", "tests/policies/added_action.dw");

        Assert.True(added.ExitCode == 0, added.Output);
        Assert.Contains("THEY DIFFER", added.Output);
        Assert.Contains("Refund", added.Output);
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
    [PythonHarness("vacuity.py")]
    public async Task LoadBearingCheckSeparatesDeadRedundantAndLive()
    {
        // A forbid on an action no permit covers. It reads like a control and denies nothing,
        // because default-deny had already shut that door.
        var forbid = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/dead_forbid.dw");

        Assert.True(forbid.ExitCode == 0, forbid.Output);
        Assert.Matches(@"permit #1\s+action == Trade\s+live", forbid.Output);
        Assert.Matches(@"forbid #2\s+action == Approve\s+DEAD", forbid.Output);

        // A gated permit sitting under an unconditional one. It fires — so it is NOT vacuous —
        // and it still decides nothing.
        var redundant = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/redundant_permit.dw");

        Assert.True(redundant.ExitCode == 0, redundant.Output);
        Assert.Matches(@"permit #2\s+action == Trade\s+REDUNDANT", redundant.Output);
        // Targets the verdict column, not the prose. A bare DoesNotContain matched the legend
        // that explains the word, which is a different thing from reporting it.
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", redundant.Output);

        // And the distinction survives: a permit a forbid always overrides is still VACUOUS,
        // not merely redundant.
        var vacuous = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/overridden_permit.dw");

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
    [PythonHarness("vacuity.py")]
    public async Task VacuityCheckerReproducesTheHandWrittenSpecsFinding()
    {
        var live = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/docs_trading.dw");

        Assert.True(live.ExitCode == 0, live.Output);
        Assert.Matches(@"action == SellShares\s+live\s+witness: ApproveSale -> SellShares", live.Output);

        // The same file with approvals forbidden instead of permitted. The SellShares permit is
        // untouched — and now grants nothing, because a denied approval is recorded as an `error`
        // and the `::response` it waits for is never written.
        var vacuous = await PythonHarness.RunAsync(
            "tests/strands/vacuity.py", "tests/policies/docs_trading_forbidden.dw");

        Assert.True(vacuous.ExitCode == 0, vacuous.Output);
        Assert.Matches(@"action == SellShares\s+VACUOUS", vacuous.Output);
    }

    /// <summary>
    /// <c>RotationPolicies.tla</c> is generated from the <c>.dw</c> sources, so it can go stale.
    /// This regenerates and compares.
    /// </summary>
    /// <remarks>
    /// The generated module is checked in, which is what lets the spec tests run in CI without a
    /// venv — but a checked-in generated file is a copy, and a copy drifts. A <c>.dw</c> edit that
    /// was never carried through would leave <c>SessionRotation</c> quietly checking the previous
    /// policy while its own source file says something else.
    /// </remarks>
    [PythonHarness("dw_to_tla.py")]
    public async Task GeneratedRotationPoliciesAreUpToDate()
    {
        var run = await PythonHarness.RunAsync("tests/strands/dw_to_tla.py", "--check");
        Assert.True(run.ExitCode == 0, run.Output);
        Assert.Contains("up to date", run.Output);
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
