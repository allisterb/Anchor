namespace Anchor.Tests.TLAPlus;

/// <summary>
/// What a policy&#39;s values become in the model: the domains a field ranges over, glob patterns,
/// address ranges, and the scope a temporal predicate can see. Each of these is a place where a
/// modelling shortcut would produce an answer about a policy nobody wrote.
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
/// This class holds 51s of the 508s. Its slowest test is
/// <c>FieldDomainsComeFromTheLiteralsThePolicyNames</c>, at 18s.
/// </para>
///
/// See <see cref="PythonHarnessAttribute"/> for why any of these may report as skipped.
/// </remarks>
public class VocabularyHarnessTests : TestsRuntime
{
    #region Methods

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
    /// A literal too large for TLC is <b>refused by name</b>, not left to fail inside the model
    /// checker.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Cedar's <c>Long</c> runs to 2^63-1 and a budget cap written in cents reaches nine figures
    /// without anyone thinking about it. TLA+ integers are unbounded — this is <b>TLC's</b> limit,
    /// not the language's: it holds them in a Java int and reserves <c>Integer.MAX_VALUE</c>, so
    /// the largest literal it accepts is 2147483646. Measured, not assumed: 2147483646 checks and
    /// 2147483647 does not.
    /// </para>
    /// <para>
    /// What this pins is the <i>shape</i> of the failure. Unrefused, it arrives as
    /// <c>Error: TLC can't handle a number this big.</c> followed by the bare number, from a run
    /// naming neither the policy nor the field, at a point where a reader has no reason to suspect
    /// the literal. The house rule is to refuse and say which construct is responsible — the
    /// policy is valid, and it is the checker that cannot take it.
    /// </para>
    /// </remarks>
    [PythonHarness("properties.py")]
    public async Task ALiteralTooBigForTlcIsRefusedByName()
    {
        var run = await PythonHarness.RunAsync(
            "src/checker/properties.py", "tests/policies/long_overflow.dw");

        // 2 is "no verdict", which is what a refusal is. Never 0, which would report a policy
        // nobody checked as a policy with nothing wrong with it.
        Assert.True(run.ExitCode == 2, run.Output);
        Assert.Contains("outside the modelled subset", run.Output);
        Assert.Contains("3000000000", run.Output);
        Assert.Contains("2147483646", run.Output);

        // The raw TLC error must NOT be what the reader sees.
        Assert.DoesNotContain("TLC can't handle a number this big", run.Output);
    }

    #endregion
}
