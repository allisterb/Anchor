namespace Anchor.Verifiers.Dafny;

using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

using Microsoft.Dafny;

using static Anchor.Result;

/// <summary>
/// Parses and type-checks Dafny source in-process via the DafnyPipeline assembly.
/// </summary>
public class DafnyProgram : Runtime
{
    #region Methods

    /// <summary>Options for a headless run. Diagnostics go to the reporter, not the console.</summary>
    public static DafnyOptions CreateOptions(params string[] args) =>
        DafnyOptions.CreateUsingOldParser(TextWriter.Null, TextReader.Null, args);

    /// <summary>Parse only. Failure carries the parser diagnostics.</summary>
    public static async Task<Result<Program>> ParseAsync(string src, string name = "program.dfy", DafnyOptions? options = null)
    {
        var reporter = new BatchErrorReporter(options ?? CreateOptions());
        var parsed = await ProgramParser.Parse(src, SourceUri(name), reporter);
        return reporter.HasErrors ? Failure<Program>(Diagnostics(reporter)) : Success(parsed.Program);
    }

    /// <summary>Parse and resolve (name resolution + type checking). Failure carries the diagnostics.</summary>
    public static async Task<Result<Program>> ResolveAsync(string src, string name = "program.dfy", DafnyOptions? options = null, CancellationToken ct = default)
    {
        var reporter = new BatchErrorReporter(options ?? CreateOptions());
        var parsed = await ProgramParser.Parse(src, SourceUri(name), reporter);
        if (reporter.HasErrors)
        {
            return Failure<Program>(Diagnostics(reporter));
        }
        await new ProgramResolver(parsed.Program).Resolve(ct);
        return reporter.CountExceptVerifierAndCompiler(ErrorLevel.Error) > 0
            ? Failure<Program>(Diagnostics(reporter))
            : Success(parsed.Program);
    }

    /// <summary>All messages the reporter collected, one per line, in Dafny's console format.</summary>
    public static string Diagnostics(BatchErrorReporter reporter) =>
        string.Join(Environment.NewLine,
            reporter.AllMessages.Select(d => ErrorReporter.FormatDiagnostic(reporter.Options, d)));

    private static Uri SourceUri(string name) => new(Path.Combine(Path.GetTempPath(), name));

    #endregion
}
