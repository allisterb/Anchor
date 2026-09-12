namespace Anchor.MCPServer;

using System;
using System.Linq;
using System.Threading.Tasks;

/// <summary>
/// Entry point. Stdio by default, because that is how an MCP host launches a server; HTTP on
/// request, because that is what a container exposes.
/// </summary>
public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args.Contains("--help") || args.Contains("-h"))
        {
            Console.WriteLine(Usage);
            return 0;
        }

        // File logging only. On stdio, stdout carries MCP frames and nothing else; on HTTP the
        // console is free, but keeping one logging configuration means the stdio path is not a
        // special case nobody exercises.
        Runtime.WithFileLogging("Anchor", "MCP", debug: args.Contains("--debug"));

        var projectDir = Value(args, "--project-dir");
        var anchorRoot = Value(args, "--anchor-root");

        try
        {
            if (args.Contains("--http"))
            {
                var port = int.TryParse(Value(args, "--port"), out var p) ? p : AnchorMCPServer.DefaultPort;
                await AnchorMCPServer.RunHttpAsync(port, projectDir, anchorRoot);
            }
            else
            {
                await AnchorMCPServer.RunStdioAsync(projectDir, anchorRoot);
            }
            return 0;
        }
        catch (Exception e)
        {
            Runtime.Fatal("The Anchor MCP server stopped: {0}", e.Message);
            Console.Error.WriteLine(e.Message);
            return 1;
        }
    }

    /// <summary>The value after <paramref name="name"/>, or null. Also accepts <c>--name=value</c>.</summary>
    static string? Value(string[] args, string name)
    {
        var inline = args.FirstOrDefault(a => a.StartsWith(name + "=", StringComparison.Ordinal));
        if (inline is not null)
        {
            return inline[(name.Length + 1)..];
        }

        var i = Array.IndexOf(args, name);
        return i >= 0 && i + 1 < args.Length && !args[i + 1].StartsWith('-') ? args[i + 1] : null;
    }

    const string Usage = """
        Anchor MCP server — model-checked verdicts on Dogwood policies.

          Anchor.MCPServer [--http [--port N]] [--project-dir DIR] [--anchor-root DIR] [--debug]

          --http            serve over HTTP instead of stdio (default port 8080)
          --port N          HTTP port
          --project-dir DIR the directory tool paths are resolved inside; paths escaping it are refused
          --anchor-root DIR the Anchor tree the Python checker is run from.
                            Defaults to $ANCHOR_ROOT, then the enclosing checkout.
          --debug           debug-level logging

        Stdio is the default because that is how an MCP host launches a server. The tools are the
        same either way.
        """;
}
