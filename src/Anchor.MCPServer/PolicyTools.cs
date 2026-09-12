namespace Anchor.MCPServer;

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Linq;
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
        "linter and it is not a retry-on-timeout call.")]
    public async Task<PolicyCheckResult> CheckPolicyAsync(
        [Description("Path to the .dw policy file, relative to the project directory.")] string policy,
        [Description("Optional second .dw file. Given one, the tool stops checking rules and instead reports a session the two policies decide DIFFERENTLY -- the question to ask before replacing a policy with an edited version.")] string? against = null,
        [Description("Path to the .dwschema event schema the policy is deployed under. Pass it whenever one exists; see the note above about the unpinned reading.")] string? eventSchema = null,
        [Description("Path to a TLA+ module of your own that extends PolicyUnderTest and states what this policy is SUPPOSED to mean, with a companion .cfg naming its invariants. Use this for a claim the three built-in findings cannot express, such as 'SSH from the local range is permitted and every external source is denied'.")] string? property = null,
        [Description("Session length bound (default 3). This is the number that makes VACUOUS provisional.")] int? attempts = null,
        [Description("Numeric domain for input fields, 1..N (default 2).")] int? amount = null,
        [Description("Refuse a policy reading more than N input/output fields (default 4). The request space is the product of their domains, so this bounds the state space rather than soundness.")] int? maxFields = null,
        [Description("Include the raw TLC output for each rule. Verbose and rarely what you want.")] bool? verbose = null,
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
        if (verbose is true) args.Add("--verbose");

        var timeout = TimeSpan.FromSeconds(timeoutSeconds ?? 600);
        var r = await PythonProcess.RunAsync(CheckerScript, [.. args], root: AnchorRoot,
            timeout: timeout, ct: cancellationToken);

        if (!r.IsSuccess)
        {
            // The checker could not be RUN. Distinct from a policy it declined to answer about, and
            // the distinction matters: one is our problem and the other is the policy's.
            return new PolicyCheckResult(false, null, [], "", r.Message ?? "the checker could not be run");
        }

        var run = r.Value;

        // Exit 2 is the house refusal: the policy uses something outside the modelled subset, and
        // the checker declines rather than approximating. Surfaced as its own state so an agent
        // does not read "no findings" as "nothing wrong".
        if (!run.Succeeded)
        {
            return new PolicyCheckResult(false, null, [], run.Output,
                Refusal(run.ErrorOutput) ?? $"the checker exited {run.ExitCode}: {run.ErrorOutput.Trim()}");
        }

        return new PolicyCheckResult(true, Reading(run.Output), [.. Findings(run.Output)], run.Output, null);
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
    [GeneratedRegex(@"^[ \t]+(?<effect>permit|forbid)[ \t]+#(?<rule>\d+)[ \t]+action == .+?[ \t]+(?<verdict>VACUOUS|REDUNDANT|DEAD|live)\b(?<note>.*)$",
        RegexOptions.Multiline)]
    private static partial Regex FindingLine();

    [GeneratedRegex(@"^under .+$", RegexOptions.Multiline)]
    private static partial Regex ReadingLine();

    #endregion

    #region Fields

    /// <summary>Relative to the Anchor root, which is where <see cref="PythonProcess"/> runs it.</summary>
    public const string CheckerScript = "src/checker/properties.py";

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
    string? Error)
{
    /// <summary>Rules that are not load-bearing. Empty on a policy where every rule matters.</summary>
    public IEnumerable<RuleFinding> Inert => Findings.Where(f => f.Verdict != "live");
}
