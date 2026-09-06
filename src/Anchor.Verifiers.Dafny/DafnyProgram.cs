namespace Anchor.Verifiers.Dafny;

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

using Microsoft.Dafny;

using Bpl = Microsoft.Boogie;

using static Anchor.Result;

/// <summary>
/// Parses, type-checks and verifies Dafny source in-process via the DafnyPipeline assembly.
/// </summary>
public class DafnyProgram : Runtime
{
    #region Methods

    /// <summary>
    /// Options for a headless run. Diagnostics go to the reporter, not the console.
    /// DafnyOptions defaults Printer to NullPrinter and only the CLI replaces it, so verification
    /// outcomes would otherwise come back with no accompanying text.
    /// </summary>
    public static DafnyOptions CreateOptions(params string[] args)
    {
        var options = DafnyOptions.CreateUsingOldParser(TextWriter.Null, TextReader.Null, args);
        options.Printer = new DafnyConsolePrinter(options);
        return options;
    }

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
        return (await ResolveAsync(src, name, reporter, ct)).Map(p => p);
    }

    /// <summary>
    /// Parse, resolve, translate to Boogie and discharge the proof obligations with the SMT solver.
    /// A <c>Failure</c> means the pipeline could not run (syntax error, type error, no solver);
    /// a <c>Success</c> whose <see cref="DafnyVerification.Verified"/> is false means it ran and the proof failed.
    /// </summary>
    public static async Task<Result<DafnyVerification>> VerifyAsync(string src, string name = "program.dfy", DafnyOptions? options = null, CancellationToken ct = default)
    {
        var reporter = new BatchErrorReporter(options ??= CreateOptions());
        if (!(await ResolveAsync(src, name, reporter, ct)).Succeeded(out var resolved))
        {
            return Failure<DafnyVerification>(resolved.Message);
        }

        // Resolves the z3 path and sets the solver options derived from its version.
        WithProject(options, SourceUri(name)).ProcessSolverOptions(reporter, Token.Cli);
        if (reporter.HasErrors)
        {
            return Failure<DafnyVerification>(Diagnostics(reporter));
        }

        var output = new StringWriter();
        var modules = new List<DafnyModuleVerification>();
        using (var engine = Bpl.ExecutionEngine.CreateWithoutSharedCache(options))
        {
            foreach (var (module, boogie) in BoogieGenerator.Translate(resolved.Value, reporter))
            {
                ct.ThrowIfCancellationRequested();
                var (outcome, stats) = await DafnyMain.BoogieOnce(reporter, options, output, engine, name, module, boogie, name);
                modules.Add(new DafnyModuleVerification(module, outcome, stats, DafnyMain.IsBoogieVerified(outcome, stats)));
            }
        }
        return Success(new DafnyVerification(modules.All(m => m.Verified), output.ToString(), modules));
    }

    /// <summary>
    /// The z3 executable Dafny would use, resolved the way Dafny itself resolves it:
    /// the <c>--solver-path</c> option, then <c>z3/bin/z3-{DafnyOptions.DefaultZ3Version}</c> next to
    /// this assembly, then <c>z3</c> on PATH. Failure carries Dafny's own remediation message.
    /// </summary>
    public static Result<string> FindSolver(DafnyOptions? options = null)
    {
        var reporter = new BatchErrorReporter(options ??= CreateOptions());
        WithProject(options, SourceUri("program.dfy")).ProcessSolverOptions(reporter, Token.Cli);
        if (reporter.HasErrors)
        {
            return Failure<string>(Diagnostics(reporter));
        }
        var path = options.ProverOptions.Find(o => o.StartsWith(ProverPath));
        return path is null
            ? Failure<string>("The solver options were processed but no prover path was set.")
            : Success(path[ProverPath.Length..]);
    }

    /// <summary>All messages the reporter collected, one per line, in Dafny's console format.</summary>
    public static string Diagnostics(BatchErrorReporter reporter) =>
        string.Join(Environment.NewLine,
            reporter.AllMessages.Select(d => ErrorReporter.FormatDiagnostic(reporter.Options, d)));

    private static async Task<Result<Program>> ResolveAsync(string src, string name, BatchErrorReporter reporter, CancellationToken ct)
    {
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

    /// <summary>
    /// Dafny only populates <c>DafnyProject</c> from the CLI, but <c>SetZ3ExecutablePath</c> reports its
    /// "Z3 is not found" error on <c>DafnyProject.StartingToken</c> — a null reference when options are
    /// built in-process. Supply the implicit project the CLI would have made.
    /// </summary>
    private static DafnyOptions WithProject(DafnyOptions options, Uri uri)
    {
        options.DafnyProject ??= new DafnyProject(null, uri, null, new HashSet<string> { uri.LocalPath })
        {
            ImplicitFromCli = true
        };
        return options;
    }

    private static Uri SourceUri(string name) => new(Path.Combine(Path.GetTempPath(), name));

    #endregion

    #region Fields

    private const string ProverPath = "PROVER_PATH=";

    #endregion
}

/// <summary>Outcome of verifying every module in a program.</summary>
public record DafnyVerification(bool Verified, string Output, IReadOnlyList<DafnyModuleVerification> Modules);

/// <summary>Outcome of verifying one module.</summary>
public record DafnyModuleVerification(string Module, Bpl.PipelineOutcome Outcome, Bpl.PipelineStatistics Statistics, bool Verified);
