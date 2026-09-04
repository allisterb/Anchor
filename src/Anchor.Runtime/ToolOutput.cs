namespace Anchor;

using System.IO;
public record ToolOutput
{
    public int ExitCode { get; }
    public string StdOut { get; }
    public string StdErr { get; }  

    public ToolOutput(int exitcode, string stdout, string stderr)
    {
        ExitCode = exitcode;    
        StdOut = stdout;
        StdErr = stderr;
    }

    public ToolOutput(int exitcode, StringWriter stdout, StringWriter stderr) : this(exitcode, stdout.ToString(), stderr.ToString()) { }

    public static (StringReader, StringWriter, StringWriter) CreateStreams(string stdin) => (new StringReader(stdin), new StringWriter(), new StringWriter());
}
