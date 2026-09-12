namespace Anchor.Tests.MCPServer;

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;

using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

using Anchor.MCPServer;

/// <summary>
/// The server driven by a real MCP client over HTTP, on an ephemeral port.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="PolicyToolTests"/> calls the tool methods directly, which proves the checker is
/// wrapped correctly but says nothing about whether an agent can reach them: the schema the server
/// advertises, the serialisation of the result, and whether a refusal arrives as an answer or as a
/// transport error are all outside that. This suite is the part an agent host actually exercises.
/// </para>
/// <para>
/// HTTP rather than stdio because it is the transport a container exposes, and because the two
/// share one registration — see <c>AnchorMCPServer.Register</c>. A stdio-only defect would have to
/// live in the transport wiring itself, which is the SDK's code rather than ours.
/// </para>
/// </remarks>
public class ProtocolTests : TestsRuntime, IAsyncLifetime
{
    #region Methods

    public async Task InitializeAsync()
    {
        app = AnchorMCPServer.BuildHttpApp(projectDir: Repo);
        app.Urls.Clear();
        app.Urls.Add("http://127.0.0.1:0");
        await app.StartAsync();

        baseUrl = app.Services.GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!.Addresses.First();
    }

    public async Task DisposeAsync()
    {
        await app.StopAsync();
        await app.DisposeAsync();
    }

    /// <summary>
    /// The tool is advertised, and advertised with the guidance that makes it usable. The
    /// description is not decoration: an agent that cannot see that VACUOUS is bounded, or that the
    /// unpinned reading is not the deployed one, will report a verdict more confidently than the
    /// verdict deserves.
    /// </summary>
    [PolicyCheck]
    public async Task TheCheckerIsAdvertisedWithItsCaveats()
    {
        await using var client = await NewClientAsync();

        var tools = await client.ListToolsAsync();
        var check = Assert.Single(tools, t => t.Name == "CheckPolicy");

        var description = check.Description ?? "";
        Assert.Contains("VACUOUS", description);
        Assert.Contains("THE BOUND IS REAL", description);
        Assert.Contains("UNPINNED", description);

        // The one required argument, and the optional ones an agent needs to know exist.
        var schema = check.JsonSchema.ToString();
        Assert.Contains("policy", schema);
        Assert.Contains("eventSchema", schema);
        Assert.Contains("attempts", schema);
    }

    /// <summary>A verdict, end to end, through the pipeline an agent host uses.</summary>
    [PolicyCheck]
    public async Task CheckPolicyReturnsAVerdictOverTheProtocol()
    {
        await using var client = await NewClientAsync();

        var r = await client.CallToolAsync("CheckPolicy", new Dictionary<string, object?>
        {
            ["policy"] = "tests/policies/dead_forbid.dw"
        });

        Assert.True(r.IsError != true, Text(r));

        var text = Text(r);
        Assert.Contains("DEAD", text);
        Assert.Contains("forbid", text);

        // The caveat has to survive serialisation too, not merely exist on the record.
        Assert.Contains("UNPINNED", text, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// A refused policy comes back as an ANSWER saying it was refused, not as a protocol error and
    /// not as an empty pass. An agent distinguishes the three differently, and only one of them is
    /// true here.
    /// </summary>
    [PolicyCheck]
    public async Task ARefusalArrivesAsAnAnswer()
    {
        await using var client = await NewClientAsync();

        var r = await client.CallToolAsync("CheckPolicy", new Dictionary<string, object?>
        {
            ["policy"] = "tests/policies/like_impossible.dw"
        });

        var text = Text(r);
        Assert.Contains("REFUSED", text);
        Assert.Contains("glob intersection", text);

        // "answered: false", not "findings: []". The difference is the whole point.
        Assert.Contains("false", text, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Containment holds across the protocol boundary. Reached this way the refusal is an argument
    /// error rather than an exception, so it must still be visibly a refusal.
    /// </summary>
    [PolicyCheck]
    public async Task APathOutsideTheProjectIsRefusedOverTheProtocol()
    {
        await using var client = await NewClientAsync();

        var r = await client.CallToolAsync("CheckPolicy", new Dictionary<string, object?>
        {
            ["policy"] = "../../CLAUDE.md"
        });

        var text = Text(r);
        Assert.True(r.IsError == true || text.Contains("outside this project's directory"),
            $"a path escaping the project was not refused: {text}");
    }

    /// <summary>
    /// The describe tool is reachable and cheap. Its whole value is being called BEFORE a property
    /// module is written, so a tool an agent cannot find is a tool that does not exist.
    /// </summary>
    [PolicyCheck]
    public async Task DescribePolicyModuleIsReachableAndFast()
    {
        await using var client = await NewClientAsync();

        var tools = await client.ListToolsAsync();
        var describe = Assert.Single(tools, t => t.Name == "DescribePolicyModule");
        Assert.Contains("Num(22)", describe.Description ?? "");

        var started = DateTime.UtcNow;
        var r = await client.CallToolAsync("DescribePolicyModule", new Dictionary<string, object?>
        {
            ["policy"] = "tests/policies/firewall.dw"
        });
        var elapsed = DateTime.UtcNow - started;

        Assert.True(r.IsError != true, Text(r));

        var text = Text(r);
        Assert.Contains("Connect", text);
        Assert.Contains("skeleton", text);
        Assert.Contains("PolicyUnderTest", text);

        // No TLC, so this is parsing only. Ten seconds is loose enough for a cold process start and
        // still catches a regression that made this run the model checker.
        Assert.True(elapsed < TimeSpan.FromSeconds(10),
            $"describe took {elapsed.TotalSeconds:0.#}s; it should not be running TLC");
    }

    /// <summary>
    /// The knowledge base over the wire, both ways it is offered. Needs no Python and no JVM, so it
    /// is a plain Fact: a host with neither should still be able to read the reference.
    /// </summary>
    [Fact]
    public async Task TheKnowledgeBaseIsReachableAsToolsAndAsResources()
    {
        await using var client = await NewClientAsync();

        var tools = await client.ListToolsAsync();
        Assert.Single(tools, t => t.Name == "ListKnowledge");
        Assert.Single(tools, t => t.Name == "ReadKnowledge");

        var listed = await client.CallToolAsync("ListKnowledge", new Dictionary<string, object?>());
        Assert.True(listed.IsError != true, Text(listed));
        Assert.Contains("reading-verdicts", Text(listed));

        var read = await client.CallToolAsync("ReadKnowledge", new Dictionary<string, object?>
        {
            ["names"] = new[] { "reading-verdicts" }
        });
        Assert.True(read.IsError != true, Text(read));
        Assert.Contains("VACUOUS", Text(read));

        // And as resources, for a host that reads those instead.
        var resources = await client.ListResourcesAsync();
        var article = Assert.Single(resources, r => r.Uri == "anchor://knowledge/reading-verdicts");

        var contents = await client.ReadResourceAsync(article.Uri);
        Assert.Contains("VACUOUS", string.Concat(contents.Contents.OfType<TextResourceContents>().Select(c => c.Text)));
    }

    async Task<McpClient> NewClientAsync()
    {
        var transport = new HttpClientTransport(
            new HttpClientTransportOptions { Endpoint = new Uri(baseUrl) },
            NullLoggerFactory.Instance);
        return await McpClient.CreateAsync(transport);
    }

    static string Text(CallToolResult r) =>
        string.Concat(r.Content.OfType<TextContentBlock>().Select(c => c.Text));

    #endregion

    #region Fields

    static readonly string Repo = PythonProcess.FindRoot().IsSuccess
        ? PythonProcess.FindRoot().Value : Directory.GetCurrentDirectory();

    WebApplication app = null!;

    string baseUrl = "";

    #endregion
}
