namespace Anchor.Tests.MCPServer;

using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;

using Anchor.MCPServer;

/// <summary>
/// <c>DescribePolicyModule</c> — what a property module may name, and whether the skeleton it hands
/// out actually works.
/// </summary>
/// <remarks>
/// The claim this tool makes is not "here is some documentation". It is that an author who follows
/// the reply gets a module that RUNS — right `EXTENDS`, right instantiation of the semantics, right
/// shape of arguments to `Decide`. Documentation that is merely plausible would be worse than none,
/// because a property module that fails to elaborate looks like a broken tool rather than a wrong
/// claim.
/// <para>
/// So the central test writes the skeleton to disk and checks the policy against it. Nothing short
/// of that distinguishes a correct description from a convincing one.
/// </para>
/// </remarks>
public class DescribeModuleTests : TestsRuntime
{
    #region Methods

    /// <summary>The vocabulary is the policy's own, not a generic list.</summary>
    [PolicyCheck]
    public async Task ItNamesThePolicysOwnVocabulary()
    {
        var d = await DescribeAsync("firewall.dw");

        Assert.Equal("firewall.dw", d.GetProperty("source").GetString());
        Assert.Equal("PolicyUnderTest", d.GetProperty("module").GetString());

        Assert.Contains("Connect", d.GetProperty("actions").EnumerateArray().Select(a => a.GetString()));

        var fields = d.GetProperty("inputFields").EnumerateArray()
            .ToDictionary(f => f.GetProperty("name").GetString()!, f => f);
        Assert.Equal(["origin", "port"], fields.Keys.Order());
        Assert.Equal("integer", fields["port"].GetProperty("kind").GetString());
        Assert.Equal("string", fields["origin"].GetProperty("kind").GetString());

        // Tagged, because an untagged 22 is the mistake this tool exists to prevent.
        var ports = fields["port"].GetProperty("domain").EnumerateArray().Select(v => v.GetString()).ToList();
        Assert.Contains("Num(22)", ports);
        Assert.DoesNotContain("22", ports);

        // Both rules, so a claim can be written about either.
        Assert.Equal(2, d.GetProperty("rules").GetArrayLength());
    }

    /// <summary>
    /// THE TEST THAT MATTERS. The skeleton is written out and checked, and must produce a verdict
    /// about the CLAIM rather than an error about the module.
    /// </summary>
    /// <remarks>
    /// The skeleton's claim is deliberately wrong — it asserts the policy grants everything, and
    /// <c>firewall.dw</c> forbids external traffic — so the expected outcome is a violation naming
    /// the offending request. A violation proves the whole path elaborated: EXTENDS resolved,
    /// DogwoodSemantics instantiated, Decide called with the right arity, the .cfg understood.
    /// </remarks>
    [PolicyCheck]
    public async Task TheSkeletonItHandsOutActuallyRuns()
    {
        var dir = Path.Combine(Path.GetTempPath(), "anchor-describe-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            // A self-contained project: the policy, and the module the description told us to write.
            File.Copy(Path.Combine(Repo, "tests", "policies", "firewall.dw"),
                      Path.Combine(dir, "firewall.dw"));

            var d = await DescribeAsync("firewall.dw");
            await File.WriteAllTextAsync(Path.Combine(dir, "firewall.tla"),
                d.GetProperty("skeleton").GetString());
            await File.WriteAllTextAsync(Path.Combine(dir, "firewall.cfg"),
                d.GetProperty("config").GetString());

            var tools = new PolicyTools(projectRoot: dir);
            var check = await tools.CheckPolicyAsync("firewall.dw", property: "firewall.tla");

            Assert.True(check.Answered, check.Error);

            // It elaborated and reached a verdict about the claim.
            Assert.Contains("EverythingIsGranted", check.Output);

            // And the verdict is the right one: the claim is false, with the request that breaks it.
            Assert.Contains("violated", check.Output, StringComparison.OrdinalIgnoreCase);
            Assert.Contains("external", check.Output);

            // Not a wiring failure dressed up as a finding.
            Assert.DoesNotContain("Unknown operator", check.Output);
            Assert.DoesNotContain("was not found", check.Output);
        }
        finally
        {
            try { Directory.Delete(dir, recursive: true); } catch (IOException) { /* scratch */ }
        }
    }

    /// <summary>
    /// The domain carries one value the policy never names, so that "does not match" is reachable.
    /// For a string that value is a NUL byte — unwritable, so it must be reported rather than
    /// offered as a literal an author might paste.
    /// </summary>
    [PolicyCheck]
    public async Task TheUnwritableSentinelIsDescribedAndNeverOffered()
    {
        var d = await DescribeAsync("firewall.dw");

        var origin = d.GetProperty("inputFields").EnumerateArray()
            .Single(f => f.GetProperty("name").GetString() == "origin");

        Assert.True(origin.GetProperty("plusOneValueThePolicyNeverNames").GetBoolean());
        Assert.Equal(["Str(\"external\")", "Str(\"local\")"],
            origin.GetProperty("domain").EnumerateArray().Select(v => v.GetString()!).Order());

        // Nowhere in anything an author is invited to copy.
        Assert.DoesNotContain('\0', d.GetProperty("skeleton").GetString()!);
        Assert.DoesNotContain('\0', d.GetRawText());
    }

    /// <summary>A policy outside the subset has no vocabulary to describe, and says so.</summary>
    [PolicyCheck]
    public async Task ARefusedPolicyIsRefusedHereToo()
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var r = await tools.DescribePolicyModuleAsync(
            Path.Combine("tests", "policies", "like_impossible.dw"));

        Assert.False(r.Answered);
        Assert.Null(r.Module);
        Assert.Contains("REFUSED", r.Error ?? "");
    }

    static async Task<JsonElement> DescribeAsync(string fixture)
    {
        var tools = new PolicyTools(projectRoot: Repo);
        var r = await tools.DescribePolicyModuleAsync(Path.Combine("tests", "policies", fixture));

        Assert.True(r.Answered, r.Error);
        Assert.NotNull(r.Module);
        return r.Module!.Value;
    }

    #endregion

    #region Fields

    static readonly string Repo = PythonProcess.FindRoot().IsSuccess
        ? PythonProcess.FindRoot().Value : Directory.GetCurrentDirectory();

    #endregion
}
