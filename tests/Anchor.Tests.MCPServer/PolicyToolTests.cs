namespace Anchor.Tests.MCPServer;

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

using Anchor.MCPServer;
using Anchor.Verifiers.TLAPlus;

/// <summary>
/// The MCP server's policy tools, held to the command line they wrap.
/// </summary>
/// <remarks>
/// <para>
/// THE POINT OF THE DIFFERENTIAL. The checker's CLI is the interface this project documents, tests
/// and reasons about; the MCP tool is a second way to reach the same code, and a second way to
/// reach the same code is a second chance to get a different answer. Argument marshalling, path
/// resolution and output parsing all sit between an agent and the verdict, and each of them could
/// silently change it — an argument dropped, a flag not forwarded, a verdict line not matched.
/// </para>
/// <para>
/// So these run both and compare. The CLI side starts its own process against the documented
/// invocation and shares nothing with <see cref="PythonProcess"/> but the interpreter path — which
/// is discovery rather than behaviour, and is not what the comparison is about.
/// </para>
/// <para>
/// SKIPPED WITHOUT THE TOOLCHAIN. The checker needs an interpreter and a JVM, because it runs TLC
/// once per rule. Skipping is visible in the run summary; passing quietly would be worse than not
/// having the test.
/// </para>
/// </remarks>
public class PolicyToolTests : TestsRuntime
{
    #region Methods

    /// <summary>Discovery, on its own, so a toolchain failure does not present as a wrong verdict.</summary>
    [PolicyCheck]
    public void TheToolchainIsFound()
    {
        var root = PythonProcess.FindRoot();
        Assert.True(root.IsSuccess, root.Message);
        Assert.True(File.Exists(Path.Combine(root.Value, "Anchor.sln")), $"not an Anchor tree: {root.Value}");

        var python = PythonProcess.FindPython();
        Assert.True(python.IsSuccess, python.Message);

        // Importable, not merely present — the modules the checker actually needs.
        Assert.True(PythonProcess.CanImport("re"), "the interpreter cannot import re");
    }

    /// <summary>
    /// The tool and the command line must produce the same text, rule for rule. Compared whole
    /// rather than verdict-by-verdict: a caveat line the tool dropped would still leave the
    /// verdicts matching, and the caveat is the part an agent most needs.
    /// </summary>
    [PolicyCheck]
    public async Task CheckPolicyAgreesWithTheCommandLine()
    {
        foreach (var fixture in new[] { "dead_forbid.dw", "redundant_permit.dw" })
        {
            var direct = await RunCheckerDirectlyAsync(fixture);
            var tool = await Tools().CheckPolicyAsync(Path.Combine("tests", "policies", fixture));

            Assert.True(tool.Answered, tool.Error);
            Assert.Equal(Normalize(direct), Normalize(tool.Output));
        }
    }

    /// <summary>
    /// The structured findings must say what the text says. Parsed here by an independent
    /// expression, so a bug in the tool's own parser cannot agree with itself.
    /// </summary>
    [PolicyCheck]
    public async Task StructuredFindingsMatchTheText()
    {
        var tool = await Tools().CheckPolicyAsync(Path.Combine("tests", "policies", "dead_forbid.dw"));
        Assert.True(tool.Answered, tool.Error);

        var fromText = Regex.Matches(tool.Output.Replace("\r\n", "\n"),
                @"^\s+(permit|forbid) #(\d+)\b.*?\s(VACUOUS|REDUNDANT|DEAD|live)\b", RegexOptions.Multiline)
            .Select(m => (Effect: m.Groups[1].Value, Rule: int.Parse(m.Groups[2].Value), Verdict: m.Groups[3].Value))
            .ToList();

        Assert.NotEmpty(fromText);
        Assert.Equal(fromText,
            tool.Findings.Select(f => (f.Effect, f.Rule, f.Verdict)).ToList());

        // The fixture's whole purpose: a forbid that denies nothing the rest of the set would allow.
        var dead = Assert.Single(tool.Inert);
        Assert.Equal("DEAD", dead.Verdict);
        Assert.Equal("forbid", dead.Effect);
    }

    /// <summary>
    /// A policy outside the modelled subset is REFUSED, and the refusal must not read as a clean
    /// bill of health. This is the failure mode that matters most: <c>Answered</c> false with an
    /// empty finding list, versus "no findings" — which an agent would summarise as "no problems".
    /// </summary>
    [PolicyCheck]
    public async Task ARefusedPolicyIsNotAnEmptyPass()
    {
        var tool = await Tools().CheckPolicyAsync(Path.Combine("tests", "policies", "like_impossible.dw"));

        Assert.False(tool.Answered);
        Assert.Empty(tool.Findings);
        Assert.NotNull(tool.Error);
        Assert.Contains("REFUSED", tool.Error);

        // The reason, not just the refusal — it names the construct, which is what makes it
        // actionable rather than a wall.
        Assert.Contains("glob intersection", tool.Error);
    }

    /// <summary>
    /// Without an event schema the checker says every answer assumes the unpinned reading, and the
    /// tool must carry that out separately. It is the single most droppable line in the output and
    /// the most expensive to drop.
    /// </summary>
    [PolicyCheck]
    public async Task TheUnpinnedCaveatSurvivesTheToolBoundary()
    {
        var tool = await Tools().CheckPolicyAsync(Path.Combine("tests", "policies", "dead_forbid.dw"));

        Assert.True(tool.Answered, tool.Error);
        Assert.NotNull(tool.Reading);
        Assert.Contains("UNPINNED", tool.Reading, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// A path escaping the project is refused. The checker prints the policy it read, so a tool
    /// that will read any file on the host is a file-disclosure tool wearing a verifier's name.
    /// </summary>
    [Fact]
    public async Task APathOutsideTheProjectIsRefused()
    {
        var tools = new PolicyTools(projectRoot: Path.Combine(Repo, "tests", "policies"));

        var escape = await Assert.ThrowsAsync<ArgumentException>(
            () => tools.CheckPolicyAsync(Path.Combine("..", "..", "CLAUDE.md")));
        Assert.Contains("outside this project's directory", escape.Message);

        // The same containment on every path-bearing parameter, not only the first.
        var viaSchema = await Assert.ThrowsAsync<ArgumentException>(
            () => tools.CheckPolicyAsync("dead_forbid.dw", eventSchema: Path.Combine("..", "..", "CLAUDE.md")));
        Assert.Contains("outside this project's directory", viaSchema.Message);
    }

    /// <summary>A missing policy is reported as such, rather than as a policy with no rules.</summary>
    [PolicyCheck]
    public async Task AMissingPolicyIsNotAnEmptyPass()
    {
        var tool = await Tools().CheckPolicyAsync(Path.Combine("tests", "policies", "no_such_policy.dw"));

        Assert.False(tool.Answered);
        Assert.Empty(tool.Findings);
        Assert.Contains("no such policy file", tool.Error ?? "");
    }

    /// <summary>
    /// The documented command line, run as a human runs it: a process of its own, arguments as the
    /// README gives them, nothing shared with the code under test but the interpreter path.
    /// </summary>
    static async Task<string> RunCheckerDirectlyAsync(string fixture)
    {
        var python = PythonProcess.FindPython();
        Assert.True(python.IsSuccess, python.Message);

        var info = new ProcessStartInfo(python.Value)
        {
            WorkingDirectory = Repo,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        info.ArgumentList.Add("src/checker/properties.py");
        info.ArgumentList.Add($"tests/policies/{fixture}");

        var output = new StringBuilder();
        using var process = new Process { StartInfo = info };
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) output.AppendLine(e.Data); };

        process.Start();
        process.BeginOutputReadLine();
        var stderr = await process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();

        Assert.True(process.ExitCode == 0, $"the checker exited {process.ExitCode}\n{output}\n{stderr}");
        return output.ToString();
    }

    static PolicyTools Tools() => new(projectRoot: Repo);

    /// <summary>Line endings only. Anything else differing is the thing being looked for.</summary>
    static string Normalize(string text) => text.Replace("\r\n", "\n").TrimEnd();

    #endregion

    #region Fields

    static readonly string Repo = PythonProcess.FindRoot().IsSuccess
        ? PythonProcess.FindRoot().Value : Directory.GetCurrentDirectory();

    #endregion
}

/// <summary>
/// A fact needing the policy checker: an interpreter and a JVM, because the checker runs TLC once
/// per rule.
/// </summary>
/// <remarks>
/// Decided at discovery, which is the only dynamic skip xunit v2 offers without another package —
/// and packages are installed by hand here, never automatically.
/// </remarks>
[AttributeUsage(AttributeTargets.Method)]
public sealed class PolicyCheckAttribute : FactAttribute
{
    public PolicyCheckAttribute()
    {
        var root = PythonProcess.FindRoot();
        var python = PythonProcess.FindPython();
        var java = TLCProcess.FindJava();

        Skip = !root.IsSuccess ? $"the policy checker needs the Anchor tree: {root.Message}"
             : !python.IsSuccess ? $"the policy checker needs Python: {python.Message}"
             : !java.IsSuccess ? $"the policy checker needs a JVM to run TLC: {java.Message}"
             : null!;
    }
}
