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
    /// Cedar's <c>ipaddr</c>: CIDR containment against Python's <c>ipaddress</c>, and a property
    /// that catches a prefix-length slip.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>This is the one part of the Dogwood model with no Dogwood oracle.</b> <c>ip(</c> and
    /// <c>isInRange</c> appear in zero <c>.dw</c> files across the whole tree — no corpus case, no
    /// example, no test — and <c>dogwood replay</c> cannot supply an address at all: its log value
    /// parser has no case for an extension value, so <c>ip("10.1.2.3")</c> in a trace becomes the
    /// <i>string</i> <c>ip("10.1.2.3")</c>, the extension call fails on the wrong type, and the
    /// policy silently does not apply. A forbid on <c>10.0.0.0/8</c> replays <c>10.1.2.3</c> as
    /// ALLOW.
    /// </para>
    /// <para>
    /// So the arithmetic is differentially tested against <c>ipaddress</c> instead — two
    /// independent implementations of one standard — and that is all it establishes. How a real
    /// deployment feeds an address in is exactly what Dogwood's own tooling cannot exercise.
    /// </para>
    /// <para>
    /// An address is four octets rather than a 32-bit number, and that is forced: TLC works in
    /// Java ints and stops at 2147483647, so <c>208.4.4.0</c> — 3489924096 — is not a value it can
    /// hold. Every octet is 0..255.
    /// </para>
    /// <para>
    /// The property half is the payoff. <c>firewall_ip_narrow.dw</c> writes <c>/9</c> where
    /// <c>/8</c> was meant, leaving the upper half of the range unblocked; every built-in check
    /// passes it — both rules fire, neither is redundant — and a spot check on 10.1.2.3 looks
    /// fine. The property names <c>10.255.255.255</c>.
    /// </para>
    /// </remarks>
    [PythonHarness("ip_differential.py")]
    public async Task IpRangeContainmentMatchesTheStandard()
    {
        var diff = await PythonHarness.RunAsync("tests/strands/ip_differential.py");

        Assert.True(diff.ExitCode == 0, diff.Output);
        Assert.Contains("AGREE on every pair", diff.Output);
        Assert.DoesNotContain("DISAGREE", diff.Output);

        // The claim holds on the policy that means what it says.
        var good = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_ip.dw",
            "--property", "tests/policies/firewall_ip.tla");

        Assert.True(good.ExitCode == 0, good.Output);
        Assert.Contains("every claim holds", good.Output);

        // A prefix-length slip that every derivable check passes.
        var narrow = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_ip_narrow.dw",
            "--property", "tests/policies/firewall_ip.tla");

        Assert.Equal(1, narrow.ExitCode);
        Assert.Contains("BlockedRangeIsRefused", narrow.Output);
        Assert.Contains("10, 255, 255, 255", narrow.Output);

        var builtin = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_ip_narrow.dw");

        Assert.True(builtin.ExitCode == 0, builtin.Output);
        Assert.Contains("every rule is load-bearing", builtin.Output);
    }

    /// <summary>
    /// A property module states what a policy is <i>supposed</i> to mean, and catches an edit the
    /// three built-in checks describe wrongly.
    /// </summary>
    /// <remarks>
    /// <para>
    /// VACUOUS, REDUNDANT/DEAD and diff are the claims statable <b>without knowing intent</b>. A
    /// property is the other kind: only the author can write it. Both extend the same generated
    /// <c>PolicyUnderTest.tla</c> — <c>Vacuity.tla</c> is itself just a property module we ship.
    /// </para>
    /// <para>
    /// <c>firewall_open.dw</c> is the point. Dropping the <c>forbid</c> and widening a permit lets
    /// the whole internet connect on port 22, and the built-in checks do <i>not</i> miss it
    /// silently — they report <b>REDUNDANT permit #1</b>, which is true, and whose advice (delete
    /// the redundant rule) shrinks the policy and leaves the hole. The redundancy is a symptom;
    /// a check that cannot know what the policy was for cannot say which of the two rules is the
    /// mistake. The property can, and names the request: port 22 from an external origin.
    /// </para>
    /// <para>
    /// Both halves are asserted. That the property holds on the good policy is worth little on its
    /// own — a claim that ranges over nothing also holds. It is the pair that means something.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task APropertyStatesWhatThePolicyIsSupposedToMean()
    {
        var good = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall.dw",
            "--property", "tests/policies/firewall.tla");

        Assert.True(good.ExitCode == 0, good.Output);
        Assert.Contains("every claim holds", good.Output);

        // The careless edit: the claim breaks, and the counterexample names the request.
        var open_ = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_open.dw",
            "--property", "tests/policies/firewall.tla");

        Assert.Equal(1, open_.ExitCode);
        Assert.Contains("OutsideIsRefused", open_.Output);
        Assert.Contains("external", open_.Output);

        // And the built-in checks on that same policy point at the WRONG rule — which is why the
        // fourth kind of check exists rather than being a nicety.
        var builtin = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_open.dw");

        Assert.True(builtin.ExitCode == 0 || builtin.ExitCode == 1, builtin.Output);
        Assert.Contains("REDUNDANT permit #1", builtin.Output);
    }

    /// <summary>
    /// A scope bind does not crash the checker, and <c>--event-schema</c> reaches the model.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <c>callerPrincipal: principal</c> is the ordinary way a policy says "the same principal did
    /// it", and it used to kill TLC outright: the synthesized events carried no <c>session</c>
    /// field, which <c>BindHolds</c> reads for every scope bind, so the run died with
    /// <c>Attempted to select nonexistent field "session"</c>. Latent because not one fixture used
    /// a scope bind — every policy here joined on payload fields instead — so it surfaced only
    /// when event schemas were wired in.
    /// </para>
    /// <para>
    /// The second half asserts the checker now states which reading produced its answers. Every
    /// verdict it had ever printed assumed the <b>unpinned</b> posture while the shipped default
    /// is <c>pinned</c>, and it said nothing about that. A tool that answers a different question
    /// than the one asked should at least say which question it answered.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task ScopeBindsWorkAndTheSchemaPostureIsStated()
    {
        var bare = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/scope_bind.dw");

        Assert.True(bare.ExitCode == 0, bare.Output);
        Assert.Matches(@"permit #1\s+action == Trade\s+live", bare.Output);
        Assert.DoesNotContain("nonexistent field", bare.Output);

        // Without a schema it must say so — the answers are for the unpinned reading.
        Assert.Contains("UNPINNED", bare.Output);

        // With one, it names the partition the deployment imposes.
        var pinned = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/scope_bind.dw",
            "--event-schema",
            "ext/dogwood/dogwood-language/configuration/event-schemas/pinned.dwschema");

        Assert.True(pinned.ExitCode == 0, pinned.Output);
        Assert.Contains("partitioned by principal", pinned.Output);
        Assert.Matches(@"permit #1\s+action == Trade\s+live", pinned.Output);
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
    [PythonHarness("properties.py")]
    public async Task LikePatternsAreEvaluatedByTheModel()
    {
        var one = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/like_prefix.dw");

        Assert.True(one.ExitCode == 0, one.Output);
        Assert.Matches(@"permit #1\s+action == SellShares\s+live", one.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", one.Output);

        // Two patterns, jointly satisfiable: a witness is constructed and the permit stays live.
        var two = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/like_two_patterns.dw");

        Assert.True(two.ExitCode == 0, two.Output);
        Assert.Matches(@"permit #1\s+action == SellShares\s+live", two.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", two.Output);

        // Two patterns no string satisfies: refused, and specifically not reported vacuous.
        var none = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/like_impossible.dw");

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
        Assert.True(int.Parse(m.Groups[1].Value) >= 37,
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

        // The second finding: one policy, one trace, two shipped event schemas, opposite verdicts.
        // A universal pin partitions the history a temporal predicate can see, and the policy text
        // says nothing about it — so asserting BOTH lines is the point. Either alone would pass
        // for a model that ignored the schema entirely.
        Assert.Matches(@"OTHER session, session-pinned\s+@1=DENY, @3=DENY", run.Output);
        Assert.Matches(@"OTHER session, unpinned\s+@1=DENY, @3=ALLOW", run.Output);
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
    [PythonHarness("properties.py")]
    public async Task FieldDomainsComeFromTheLiteralsThePolicyNames()
    {
        var strings = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/string_output.dw");

        Assert.True(strings.ExitCode == 0, strings.Output);
        Assert.Matches(@"permit #2\s+action == Read\s+live", strings.Output);
        Assert.DoesNotMatch(@"permit #\d+\s+action == \w+\s+VACUOUS", strings.Output);

        // The docs' trading example reads an input field and an output field, and joins on the
        // input — so it only works if the two move independently.
        var trading = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading.dw");

        Assert.True(trading.ExitCode == 0, trading.Output);
        Assert.Matches(@"permit #2\s+action == SellShares\s+live", trading.Output);
    }

    /// <summary>
    /// Permissiveness: did this edit <b>add</b> permissions, <b>remove</b> them, both, or
    /// neither? The question a policy author actually has when editing a set somebody else
    /// wrote — and "did they differ" is the weaker version of it that nobody can act on.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Same mechanism as the load-bearing check — compare two policy sets at every decision
    /// across every session — differing only in where the second set comes from. That is why
    /// there is no separate spec: a duplicated session model would drift, and this repo already
    /// carries <c>src/translator/dw_to_tla.py --check</c> because copies drift. The direction
    /// comes from splitting one <c>mattered</c> flag into <c>widened</c> and <c>narrowed</c>,
    /// each recorded only at a session's FIRST divergence — past that point the exploration is
    /// walking a history the other set would never have produced, so a later disagreement is not
    /// evidence about it.
    /// </para>
    /// <para>
    /// The vocabulary is Cedar Analysis's — Equivalent / More Permissive / Less Permissive /
    /// Incomparable — because agreeing with the neighbouring tool costs nothing. What differs is
    /// the domain: Cedar compares a policy as a function of one <i>request</i>, and this compares
    /// over <i>sessions</i>, which is the only way a rate limit or an approval window is visible
    /// at all.
    /// </para>
    /// <para>
    /// <b>EQUIVALENT is the answer that must never be wrong</b>, because it tells someone their
    /// edit was safe. It rests on the action vocabulary being the <b>union</b> of both files:
    /// take it from the first alone and an action only the second mentions is never attempted,
    /// so the run reports no difference having never looked. The last case below pins exactly
    /// that, and dropping the union turns it red.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task PolicyComparisonReportsWhichDirectionAnEditMoved()
    {
        // One line apart: approvals permitted, versus forbidden. The first allows strictly more.
        var wider = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading.dw",
            "--against", "tests/policies/docs_trading_forbidden.dw");

        Assert.True(wider.ExitCode == 0, wider.Output);
        Assert.Contains("MORE PERMISSIVE", wider.Output);
        Assert.Contains("ApproveSale", wider.Output);

        // THE SAME PAIR, SWAPPED. Antisymmetry is the cheapest real check available on a
        // directional verdict: a bug that reported one direction regardless of argument order
        // would pass every assertion above and fail here. The witness must survive the swap too,
        // because it is the same session being described from the other side.
        var narrower = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading_forbidden.dw",
            "--against", "tests/policies/docs_trading.dw");

        Assert.True(narrower.ExitCode == 0, narrower.Output);
        Assert.Contains("LESS PERMISSIVE", narrower.Output);
        Assert.Contains("ApproveSale", narrower.Output);
        Assert.DoesNotContain("MORE PERMISSIVE", narrower.Output);

        // Deleting the rule the checker called REDUNDANT. The two findings check each other:
        // "removing this changes no verdict" and "these files decide identically" are the same
        // claim from opposite ends, so a disagreement would mean one of them is wrong.
        var same = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/redundant_permit.dw",
            "--against", "tests/policies/redundant_permit_minimal.dw");

        Assert.True(same.ExitCode == 0, same.Output);
        Assert.Contains("EQUIVALENT", same.Output);
        Assert.DoesNotContain("PERMISSIVE", same.Output);

        // The difference is on an action only the SECOND file mentions, so this passes only if
        // the vocabulary spans both.
        var added = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/redundant_permit_minimal.dw",
            "--against", "tests/policies/added_action.dw");

        Assert.True(added.ExitCode == 0, added.Output);
        Assert.Contains("LESS PERMISSIVE", added.Output);
        Assert.Contains("Refund", added.Output);

        // THE ONLY CASE THAT COVERS THE ~Diverged GUARD, and it exists because nothing else did:
        // removing the guard leaves every assertion above green. Here a session widens at the
        // first attempt (Trade, newly permitted) and then appears to narrow at the second, on a
        // history only the NEW policy can produce — the old one denied the trade, so the forbid
        // that fires here never arms there. Counting the second observation reports INCOMPARABLE
        // on the strength of a trajectory the old policy cannot reach.
        var firstDivergenceOnly = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/edit_diverges_both_ways.dw",
            "--against", "tests/policies/edit_diverges_both_ways_old.dw");

        Assert.True(firstDivergenceOnly.ExitCode == 0, firstDivergenceOnly.Output);
        Assert.Contains("MORE PERMISSIVE", firstDivergenceOnly.Output);
        Assert.DoesNotContain("INCOMPARABLE", firstDivergenceOnly.Output);
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
    /// The worked example under <c>examples/aws1</c>: AWS's published AgentCore temporal policies,
    /// and the two findings that only an <b>intentional</b> property can reach.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Pinned as a test because it is the project's headline claim and the most expensive thing to
    /// discover twice. Both halves matter: the derived questions must keep <b>passing</b> the
    /// policy set — that is what makes the intentional failures meaningful — and the intentional
    /// claims must keep failing for the reasons stated in that directory's README.
    /// </para>
    /// <para>
    /// The positive claims are asserted too. A property module that broke everything would more
    /// likely be wrong about the policy than the policy about itself, so <c>BothIsAllowed</c>
    /// holding is what licenses reading the rest as findings rather than as noise.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task TheAwsExampleFindsWhatOnlyIntentCanFind()
    {
        // The derived questions PASS the set as deployed. This is the control.
        var derived = await PythonHarness.RunAsync(
            "src/checker/properties.py", "examples/aws1/agent-policy.dw", "--attempts", "4");

        Assert.True(derived.ExitCode == 0, derived.Output);
        Assert.Contains("every rule is load-bearing", derived.Output);
        Assert.DoesNotContain("VACUOUS", derived.Output);

        // Policy 7, against the sentence the article prints beside it. `unless` blocks the rule
        // when its body holds, so this permits writes only while the advisor is ABSENT.
        var decay = await PythonHarness.RunAsync(
            "src/checker/properties.py", "examples/aws1/07-trust-decay.dw",
            "--property", "examples/aws1/TrustDecay.tla");

        Assert.True(decay.ExitCode == 1, decay.Output);
        Assert.Contains("BROKEN", decay.Output);
        // The counterexample must be visible: a violation nobody can see is not evidence.
        Assert.Matches(@"gap = \d+", decay.Output);

        // The two trade protections are alternatives, not requirements.
        var gate = await PythonHarness.RunAsync(
            "src/checker/properties.py", "examples/aws1/agent-policy.dw",
            "--property", "examples/aws1/TradeGate.tla");

        Assert.True(gate.ExitCode == 1, gate.Output);
        Assert.Contains("BROKEN", gate.Output);
        Assert.Contains("prereq = ", gate.Output);

        // A fragment alone is VACUOUS, and the blame names the gate that never opens rather than
        // leaving the reader to work it out.
        var alone = await PythonHarness.RunAsync(
            "src/checker/properties.py", "examples/aws1/03-data-freshness.dw");

        Assert.True(alone.ExitCode == 0, alone.Output);
        Assert.Contains("VACUOUS", alone.Output);
        Assert.Contains("because: formerly within 30s get_market_price::response", alone.Output);
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
    /// The witness is told as a SESSION — the calls made, the values passed, and which were
    /// allowed — rather than as a list of action names.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <c>witness: Connect</c> is true and nearly useless: it names the action and drops the
    /// values, so it cannot say whether the connection that got through came from inside the
    /// network or outside it. That distinction is the entire content of a firewall policy.
    /// </para>
    /// <para>
    /// <b>Addresses are the case worth pinning.</b> TLC works in Java ints and stops at
    /// 2147483647, so an IPv4 address cannot be held as a 32-bit number and is modelled as four
    /// octets. Rendering that back as <c>[10, 0, 0, 0]</c> would be accurate and unreadable; the
    /// narrative prints <c>10.0.0.0</c>.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task TheWitnessIsToldAsASessionWithItsValues()
    {
        var run = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/firewall_ip.dw");

        Assert.True(run.ExitCode == 0, run.Output);

        // Dotted quad, not a list of octets and not a 32-bit integer.
        Assert.Matches(@"Connect\(src = \d+\.\d+\.\d+\.\d+\)", run.Output);
        Assert.DoesNotContain("src = [", run.Output);

        // The outcome of each attempt, which is what makes it a story rather than a list. The
        // forbid is live because it DENIES, the permit because it ALLOWS — so both words appear,
        // and a rendering that hardcoded either would fail here.
        Assert.Contains("denied", run.Output);
        Assert.Contains("allowed", run.Output);
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

    /// <summary>
    /// The same verdict as <see cref="PolicyComparisonReportsWhichDirectionAnEditMoved"/>, but as
    /// JSON carrying the witness as structured EVENTS — for a reader that has to act on the answer
    /// rather than read it.
    /// </summary>
    /// <remarks>
    /// <para>
    /// <b>The prose summary loses exactly what a repair loop needs.</b> "ApproveSale" names the
    /// action and drops the values, so it cannot say which input reached the decision — and an
    /// agent asked to fix the policy has to know whether the session that slipped through carried
    /// port 22 or port 3389. This asserts the values survive.
    /// </para>
    /// <para>
    /// Also asserts stdout is JSON and <i>only</i> JSON. The prose reading is printed before the
    /// verdict on the normal path, and leaving it in front of the document would make every
    /// caller strip a preamble before parsing — the same class of bug as a stray
    /// <c>Console.WriteLine</c> in the stdio transport.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task PolicyComparisonEmitsTheWitnessAsStructuredEvents()
    {
        var run = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/docs_trading.dw",
            "--against", "tests/policies/docs_trading_forbidden.dw", "--json");

        Assert.True(run.ExitCode == 0, run.Output);

        // Parses as a whole document, so nothing precedes or follows it.
        using var doc = System.Text.Json.JsonDocument.Parse(run.Output);
        var root = doc.RootElement;

        Assert.Equal("MORE PERMISSIVE", root.GetProperty("verdict").GetString());
        Assert.True(root.GetProperty("bound").GetProperty("exhaustive").GetBoolean());

        // The direction that found nothing is null rather than absent or an empty object: a caller
        // must be able to tell "no permissions removed" from "this field was not computed".
        Assert.Equal(System.Text.Json.JsonValueKind.Null, root.GetProperty("removed").ValueKind);

        var session = root.GetProperty("added").GetProperty("session");
        Assert.True(session.GetArrayLength() >= 1, run.Output);

        var first = session[0];
        Assert.Equal("ApproveSale", first.GetProperty("action").GetString());
        Assert.Equal("request", first.GetProperty("kind").GetString());

        // THE POINT OF THE WHOLE THING: the input VALUES, which the prose form discards. `stock`
        // is the field docs_trading.dw joins on, and it arrives as a plain number rather than as
        // the tagged {k,v} record the model uses internally.
        Assert.Equal(System.Text.Json.JsonValueKind.Number,
            first.GetProperty("input").GetProperty("stock").ValueKind);
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
        var run = await PythonHarness.RunAsync("src/translator/dw_to_tla.py", "--check");
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
