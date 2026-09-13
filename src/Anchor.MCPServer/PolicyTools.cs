namespace Anchor.MCPServer;

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

using ModelContextProtocol.Server;

/// <summary>
/// The policy-checking tools: Dogwood policy text in, a model-checked verdict out.
/// </summary>
/// <remarks>
/// Every tool here runs the Python checker out of process through <see cref="PythonProcess"/>. That
/// is not a stopgap — see its remarks — and it means a tool call costs a process start plus however
/// long TLC takes, which is seconds rather than milliseconds. Tool descriptions say so, because an
/// agent that expects a millisecond call will retry a slow one.
/// </remarks>
[McpServerToolType]
public partial class PolicyTools : Runtime
{
    #region Constructors

    public PolicyTools(string? projectRoot = null, string? anchorRoot = null)
    {
        ProjectRoot = projectRoot is null ? null : Path.GetFullPath(projectRoot);
        AnchorRoot = anchorRoot;
    }

    #endregion

    #region Properties

    /// <summary>The directory agent-supplied paths are resolved inside. Null means no containment.</summary>
    public string? ProjectRoot { get; }

    /// <summary>The Anchor tree the checker is run from. Null lets <see cref="PythonProcess"/> find it.</summary>
    public string? AnchorRoot { get; }

    #endregion

    #region Methods

    [McpServerTool(Name = "CheckPolicy")]
    [Description(
        "Model-checks a Dogwood (.dw) policy file and reports, rule by rule, whether each one is " +
        "load-bearing. Three findings are possible and they are not stylistic: VACUOUS means a permit " +
        "never grants anything in any session -- that is zero control rather than weak control, and " +
        "nothing in the policy text says so, because it parses and it validates. REDUNDANT means a " +
        "permit fires but another permit always would too. DEAD means a forbid never denies anything " +
        "the rest of the set would have allowed. 'live' means the rule changes some verdict, and the " +
        "witness names the session that proves it.\n\n" +
        "THE BOUND IS REAL. VACUOUS means 'no session of up to `attempts` attempts makes it fire', not " +
        "'never'. Raise `attempts` to trade runtime for confidence, and report the bound alongside the " +
        "verdict rather than stating the verdict flatly.\n\n" +
        "PASS `eventSchema` WHENEVER ONE EXISTS. Without it every answer assumes the UNPINNED reading " +
        "(one global trace), and the shipped default partitions history by principal. A rule reported " +
        "live under the unpinned reading may never fire under the deployed one. The tool echoes which " +
        "reading it used; do not drop that from your summary.\n\n" +
        "This runs TLC once per rule, so expect seconds to minutes, not milliseconds. It is not a " +
        "linter and it is not a retry-on-timeout call.\n\n" +
        "IF IT DOES NOT FINISH, use `smoke` rather than lowering `attempts`. See that argument.")]
    public async Task<PolicyCheckResult> CheckPolicyAsync(
        [Description("Path to the .dw policy file, relative to the project directory.")] string policy,
        [Description("Optional second .dw file -- the version being replaced. Given one, the tool stops checking rules and instead reports whether `policy` is MORE PERMISSIVE, LESS PERMISSIVE, EQUIVALENT or INCOMPARABLE to it, with a witness session for each direction. This is the question to ask about an EDIT. Report the direction, never just that they differ: a permission removed is a support ticket, a permission silently added is an incident.")] string? against = null,
        [Description("Path to the .dwschema event schema the policy is deployed under. Pass it whenever one exists; see the note above about the unpinned reading.")] string? eventSchema = null,
        [Description("Path to a TLA+ module of your own that extends PolicyUnderTest and states what this policy is SUPPOSED to mean, with a companion .cfg naming its invariants. Use this for a claim the three built-in findings cannot express, such as 'SSH from the local range is permitted and every external source is denied', or any claim about TIMING, which the built-in questions cannot reach.\n\nPASS THE PATH AND NOTHING ELSE. You do not need to read the module first and you must not ask the user to paste it; this tool reads it. When an invariant is violated the reply quotes its definition back to you, which is what tells you WHICH DIRECTION failed -- a violated claim of the form `X => allowed` means the policy DENIED, and the name alone will not tell you that.")] string? property = null,
        [Description("Session length bound (default 3). This is the number that makes VACUOUS provisional.")] int? attempts = null,
        [Description("Numeric domain for input fields, 1..N (default 2).")] int? amount = null,
        [Description("Refuse a policy reading more than N input/output fields (default 4). The request space is the product of their domains, so this bounds the state space rather than soundness.")] int? maxFields = null,
        [Description("Include the raw TLC output for each rule. Verbose and rarely what you want.")] bool? verbose = null,
        [Description(
            "Return the result as JSON with the witness as STRUCTURED EVENTS -- action, kind, time " +
            "and the input/output values -- instead of a one-line summary like 'Approve -> Trade'. " +
            "Only meaningful together with `against`.\n\n" +
            "Use this when you need to ACT on the witness rather than quote it: to say which input " +
            "reached the decision, to propose a fix, or to re-check after editing. The prose " +
            "summary names the actions and drops the values, so it cannot tell you that the session " +
            "that slipped through had port 22 rather than 3389.")] bool? trace = null,
        [Description(
            "Directory to keep the generated TLA+ in, instead of discarding it: the module built " +
            "from the policy text, the .cfg with the bounds, the raw TLC output, and a README " +
            "saying how to re-run it by hand.\n\n" +
            "For a reader who knows TLA+ and wants to check the model rather than take the verdict " +
            "on trust. Offer it when someone disputes a result. The path is resolved inside the " +
            "project directory and refused if it escapes.")] string? keep = null,
        [Description(
            "Run TLC as a random walk of N behaviours instead of exhaustively -- for a model too " +
            "big to exhaust, which is what raising `attempts` eventually produces. Try 1000.\n\n" +
            "READ THE RESULT DIFFERENTLY. A smoke run reports only `live` or `unknown`. `live` is " +
            "SOUND -- a witness is a witness however it was found, so the rule really does change " +
            "a verdict. `unknown` is NOT a finding: it means this random walk did not reach a " +
            "session where the rule matters, never that no such session exists. A smoke run can " +
            "never report VACUOUS, REDUNDANT or DEAD, because those are claims of ABSENCE and a " +
            "random walk cannot establish absence.\n\n" +
            "So: never summarise `unknown` as 'the rule is fine' or as 'the rule is inert', and " +
            "never suggest deleting a rule on the strength of it. Re-run without `smoke` for a " +
            "verdict, or raise N to search further.")] int? smoke = null,
        [Description("Seconds to allow before giving up (default 600).")] int? timeoutSeconds = null,
        CancellationToken cancellationToken = default)
    {
        var args = new List<string> { Resolve(policy, nameof(policy)) };

        Add(args, "--against", against, nameof(against));
        Add(args, "--event-schema", eventSchema, nameof(eventSchema));
        Add(args, "--property", property, nameof(property));

        if (attempts is int a) args.AddRange(["--attempts", a.ToString()]);
        if (amount is int m) args.AddRange(["--amount", m.ToString()]);
        if (maxFields is int f) args.AddRange(["--max-fields", f.ToString()]);
        if (smoke is int s) args.AddRange(["--smoke", s.ToString()]);
        if (verbose is true) args.Add("--verbose");

        // `--json` replaces the whole of stdout, the prose reading included, so the parsing below
        // must not also try to read findings out of it. `Findings` stays empty and the JSON is
        // carried in `Output` for the caller to parse -- which is what asked for it.
        if (trace is true) args.Add("--json");

        // Contained like every other path, but with the WRITE verb: this one is created, not read,
        // and an agent choosing where a tool writes is exactly the case containment exists for.
        if (!string.IsNullOrWhiteSpace(keep))
        {
            args.AddRange(["--keep", ProjectPath.Resolve(ProjectRoot, keep, nameof(keep), "Write")]);
        }

        var timeout = TimeSpan.FromSeconds(timeoutSeconds ?? 600);
        var r = await PythonProcess.RunAsync(CheckerScript, [.. args], root: AnchorRoot,
            timeout: timeout, ct: cancellationToken);

        if (!r.IsSuccess)
        {
            // The checker could not be RUN. Distinct from a policy it declined to answer about, and
            // the distinction matters: one is our problem and the other is the policy's.
            return new PolicyCheckResult(false, null, [], "", r.Message ?? "the checker could not be run", null);
        }

        var run = r.Value;
        if (!Answered(run))
        {
            return new PolicyCheckResult(false, null, [], run.Output,
                Refusal(run.ErrorOutput) ?? $"the checker exited {run.ExitCode}: {run.ErrorOutput.Trim()}",
                run.ExitCode);
        }

        return new PolicyCheckResult(true, Reading(run.Output), [.. Findings(run.Output)], run.Output, null,
            run.ExitCode);
    }

    [McpServerTool(Name = "DescribePolicyModule")]
    [Description(
        "Describes what a custom TLA+ property module may name for one policy, and returns a " +
        "skeleton module that already runs. Use this BEFORE writing anything for `CheckPolicy`'s " +
        "`property` argument -- that argument asks you to write TLA+ against a module Anchor " +
        "GENERATES from the policy, and its vocabulary is derived from that policy's own text, so " +
        "it cannot be guessed.\n\n" +
        "The reply gives the action names, the input and output field names with each field's " +
        "domain, the pin keys, the rule list, and the tagged-value constructors. Values are " +
        "TAGGED: write `Num(22)`, never `22`, and an address is four octets via `Addr(a,b,c,d)` " +
        "because TLC works in Java ints and cannot hold one as a 32-bit number.\n\n" +
        "THE TRAP THIS EXISTS TO PREVENT. There is deliberately no `Inputs` set to quantify over. " +
        "A request space derived from the policy's own literals cannot test a claim about a value " +
        "the policy never mentions -- the value is absent from the vocabulary, so the claim ranges " +
        "over nothing and PASSES having examined nothing. State the requests your claim is about, " +
        "including values the policy never names. `plusOneValueThePolicyNeverNames` tells you the " +
        "model already admits one such value internally, but it is not writable.\n\n" +
        "Cheap: this parses only and runs no TLC, so it returns in well under a second. Unlike " +
        "CheckPolicy, it answers nothing about whether the policy is correct.")]
    public async Task<PolicyModuleDescription> DescribePolicyModuleAsync(
        [Description("Path to the .dw policy file, relative to the project directory.")] string policy,
        [Description("Path to the .dwschema event schema. It changes the vocabulary -- a universal pin adds partition keys -- so pass it whenever one exists.")] string? eventSchema = null,
        [Description("Numeric domain for input fields, 1..N (default 2). Widens the domains reported here.")] int? amount = null,
        [Description("Refuse a policy reading more than N input/output fields (default 4).")] int? maxFields = null,
        CancellationToken cancellationToken = default)
    {
        var args = new List<string> { Resolve(policy, nameof(policy)), "--describe" };

        Add(args, "--event-schema", eventSchema, nameof(eventSchema));
        if (amount is int m) args.AddRange(["--amount", m.ToString()]);
        if (maxFields is int f) args.AddRange(["--max-fields", f.ToString()]);

        // No TLC here, so a minute is already generous; a policy that takes longer than this to
        // PARSE is a bug rather than a big model.
        var r = await PythonProcess.RunAsync(CheckerScript, [.. args], root: AnchorRoot,
            timeout: TimeSpan.FromMinutes(1), ct: cancellationToken);

        if (!r.IsSuccess)
        {
            return new PolicyModuleDescription(false, null, r.Message ?? "the checker could not be run");
        }

        var run = r.Value;
        if (!Answered(run))
        {
            return new PolicyModuleDescription(false, null,
                Refusal(run.ErrorOutput) ?? $"the checker exited {run.ExitCode}: {run.ErrorOutput.Trim()}");
        }

        // Passed through rather than re-modelled in C#. The checker emits this document, so a field
        // added there reaches the agent without a second definition here to keep in step — the kind
        // of drift the rest of this project spends its tests preventing.
        try
        {
            return new PolicyModuleDescription(true, JsonSerializer.Deserialize<JsonElement>(run.Output), null);
        }
        catch (JsonException e)
        {
            return new PolicyModuleDescription(false, null,
                $"the checker's --describe output was not valid JSON: {e.Message}");
        }
    }

    /// <summary>The rule-by-rule findings in the checker's output.</summary>
    /// <remarks>
    /// Parsed from the printed table rather than from a machine format, because the checker's CLI is
    /// the contract we already have and inventing a second one would be a second thing to keep true.
    /// Anything unparsed is simply absent from the list — <see cref="PolicyCheckResult.Output"/> is
    /// returned whole alongside it, so a changed format degrades to "fewer structured findings"
    /// rather than to a wrong answer.
    /// </remarks>
    public static IEnumerable<RuleFinding> Findings(string output) =>
        FindingLine().Matches(output).Select(m => new RuleFinding(
            int.Parse(m.Groups["rule"].Value),
            m.Groups["effect"].Value,
            m.Groups["verdict"].Value,
            m.Groups["note"].Value.Trim()));

    /// <summary>
    /// Which reading produced the answers — the line the checker prints before anything else.
    /// </summary>
    /// <remarks>
    /// Kept as its own field because it is the single most droppable part of the output and the most
    /// expensive to drop: a verdict computed for the unpinned reading, reported without it, reads as
    /// a verdict about the deployed configuration.
    /// </remarks>
    public static string? Reading(string output)
    {
        var text = output.Replace("\r\n", "\n");
        var match = ReadingLine().Match(text);
        if (match.Success)
        {
            return match.Value.Trim();
        }
        return text.Contains("assumes the UNPINNED reading")
            ? "no event schema given, so every answer assumes the UNPINNED reading (global trace); " +
              "the shipped default partitions by principal, under which a rule reported live here may never fire"
            : null;
    }

    /// <summary>Did the checker reach a verdict, whatever the verdict was?</summary>
    /// <remarks>
    /// The checker's exit code says whether it ANSWERED, not whether the answer was good news:
    /// <list type="bullet">
    /// <item><c>0</c> — answered. Covers findings: a VACUOUS permit, a DEAD forbid, two policies
    /// that differ. A finding is not an error.</item>
    /// <item><c>1</c> — answered, and a <c>--property</c> claim is BROKEN. The most useful answer
    /// the tool can give, and the reason this is not "nonzero means failure": treating it as a
    /// failure reports a policy that provably violates its own stated meaning as a tool that would
    /// not run.</item>
    /// <item><c>2</c> — did NOT answer. The file is missing, or the policy is outside the modelled
    /// subset and the checker refused rather than approximating.</item>
    /// </list>
    /// </remarks>
    static bool Answered(PythonRun run) => run.ExitCode != DidNotAnswer;

    static string? Refusal(string stderr)
    {
        var text = stderr.Replace("\r\n", "\n").Trim();
        return text.StartsWith("REFUSED:") || text.StartsWith("no such policy file:") ? text : null;
    }

    void Add(List<string> args, string flag, string? path, string parameter)
    {
        if (!string.IsNullOrWhiteSpace(path))
        {
            args.AddRange([flag, Resolve(path, parameter)]);
        }
    }

    /// <summary>
    /// A path as the agent wrote it, resolved inside the project. Containment applies to reads:
    /// a checker that will read any file on the host is a file-disclosure tool wearing a verifier's
    /// name, since the policy text comes back in the output.
    /// </summary>
    string Resolve(string path, string parameter) =>
        ProjectPath.Resolve(ProjectRoot, path, parameter, "Read");

    // "  permit #1  action == Connect       live      witness: Connect"
    // Anchored on the verdict word rather than on column positions: the label is padded to 34 and a
    // longer one simply runs into the verdict with no separator at all.
    [GeneratedRegex(@"^[ \t]+(?<effect>permit|forbid)[ \t]+#(?<rule>\d+)[ \t]+action == .+?[ \t]+(?<verdict>VACUOUS|REDUNDANT|DEAD|unknown|live)\b(?<note>.*)$",
        RegexOptions.Multiline)]
    private static partial Regex FindingLine();

    [GeneratedRegex(@"^under .+$", RegexOptions.Multiline)]
    private static partial Regex ReadingLine();

    #endregion

    #region Fields

    /// <summary>Relative to the Anchor root, which is where <see cref="PythonProcess"/> runs it.</summary>
    public const string CheckerScript = "src/checker/properties.py";

    /// <summary>The unattended directory check. Relative to the Anchor root, like the checker.</summary>
    public const string AutoScript = "src/agent/auto.py";

    /// <summary>The one exit code that means no verdict was reached. See <c>Answered</c>.</summary>
    public const int DidNotAnswer = 2;

    #endregion
}

/// <summary>One rule's verdict. <paramref name="Verdict"/> is VACUOUS, REDUNDANT, DEAD or live.</summary>
public record RuleFinding(int Rule, string Effect, string Verdict, string Note);

/// <summary>
/// What the checker said. <paramref name="Answered"/> false means no verdict was produced — either
/// the checker could not run or it refused the policy — and <paramref name="Error"/> says which.
/// </summary>
public record PolicyCheckResult(
    bool Answered,
    string? Reading,
    IReadOnlyList<RuleFinding> Findings,
    string Output,
    string? Error,
    int? ExitCode = null)
{
    /// <summary>
    /// A <c>property</c> claim was checked and is VIOLATED. The most useful answer the checker
    /// gives, so it is carried rather than left to be read back out of the text. A null
    /// <paramref name="ExitCode"/> means the checker never ran at all.
    /// </summary>
    public bool PropertyBroken => ExitCode == 1;

    /// <summary>Rules that are not load-bearing. Empty on a policy where every rule matters.</summary>
    public IEnumerable<RuleFinding> Inert =>
        Findings.Where(f => f.Verdict is not ("live" or "unknown"));

    /// <summary>
    /// Rules a smoke run could not settle. NOT findings: `unknown` means the random walk did not
    /// reach a session where the rule matters, never that no such session exists. Reporting these
    /// as deletable would be advice to delete a working rule.
    /// </summary>
    public IEnumerable<RuleFinding> Unsettled => Findings.Where(f => f.Verdict == "unknown");
}

/// <summary>
/// What a property module may name for one policy. <paramref name="Module"/> is the checker's own
/// <c>--describe</c> document, passed through verbatim.
/// </summary>
public record PolicyModuleDescription(bool Answered, JsonElement? Module, string? Error);
