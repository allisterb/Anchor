# Anchor

A formal verification framework for [Amazon Strands SDK](https://strandsagents.com/) multi-agent
workflows.

Anchor models an agent workflow as a state machine that can be checked before it is run. TLA+ is
used to verify the workflow's logic — safety and liveness of the agent protocol — and Dafny to write
the workflow implementation itself, which is then translated to Python on the Strands SDK. The goal
is that, given the stated assumptions hold, the generated agent code is provably well-behaved rather
than merely tested.

Both humans and agents are meant to author these models, so the verifiers are exposed as a library
rather than as a wrapper around a command line.

## Status

Milestone 1 — confirm the Dafny and TLA+ toolchains work end to end — is complete.

| | Parse | Type check | Verify / model check |
|---|---|---|---|
| **Dafny** | in-process | in-process | in-process |
| **TLA+** | in-process (SANY) | — | out-of-process (TLC) |

## Prerequisites

- **.NET 10 SDK.** The projects target `net10.0` and use C# 14.
- **A JDK, Java 11 or later**, on `JAVA_HOME` or `PATH`. TLC is run out-of-process on a real JVM, so
  a JVM has to be there. **The build scripts do not install this** — they check for it and stop if
  it is missing. Everything else they fetch themselves.

## Building

```
./build.sh -t          # Linux, macOS, or git bash on Windows
./build.ps1 -Test      # PowerShell
```

Run either with `-h` for the full options. Both scripts fetch the native dependencies into `lib/`,
verify them, build the solution, and — with `-t` / `-Test` — run the tests. `lib/` is gitignored, so
a fresh clone needs one of these before its first build.

| | |
|---|---|
| `-c` / `-Configuration` | `Debug` (default) or `Release` |
| `-t` / `-Test` | run the tests after building |
| `-s` / `-SkipDependencies` | don't download; files already present are still verified |
| `-f` / `-Force` | re-download even when present and matching |
| `-h` / `-Help` | usage |

### What gets fetched

Two native binaries that NuGet cannot supply:

- **z3 4.12.1**, the solver Dafny shells out to. Taken from
  [dafny-lang/solver-builds](https://github.com/dafny-lang/solver-builds) — the build Dafny itself is
  tested against — rather than the upstream Z3Prover release. Note that Dafny drives the solver as a
  subprocess over SMT-LIB2 and never touches the Z3 managed API, so the `Microsoft.Z3` NuGet packages
  are no substitute: they ship `libz3.dll`, not an executable.
- **tla2tools 1.7.4**, used two ways — cross-compiled by IKVM for in-process SANY, and run on a real
  JVM for TLC.

Both are checked against pinned sha256 hashes on every run, whether just downloaded or already
present, and a mismatch stops the build rather than being repaired silently.

**z3 is pinned per platform.** Each OS gets a different binary from solver-builds, so one hash cannot
cover them all, and solver-builds publishes no checksums of its own. Windows and Linux (x64) are
recorded and both are built and tested in CI. macOS is not: on an unpinned platform the scripts stop
and explain how to record a hash rather than installing an unverified solver.

## Layout

| Path | |
|---|---|
| `src/Anchor.Runtime` | base types for every other project — `Runtime` and its logging, `Result<T>`, process helpers |
| `src/Anchor.Verifiers.Dafny` | parse, resolve and verify Dafny via the DafnyPipeline assembly |
| `src/Anchor.Verifiers.TLAPlus` | SANY in-process via IKVM; TLC out-of-process via `TLCProcess` |
| `tests/Anchor.Tests.Verifier` | tests for both verifiers |
| `requirements/` | Python dependencies, pinned and hash-locked |
| `python/` | the Python venv the Strands SDK is installed into (gitignored) |
| `lib/` | native dependencies, fetched by the build scripts (gitignored) |
| `reference/` | third-party source read for reference, never built (gitignored) |

## Python

The Strands SDK is the target the Dafny workflows are translated to, and lives in a venv at
`python/`, separate from the .NET build and installed by hand rather than by the build scripts.

It is installed with pip in hash-checking mode and wheels-only: an install either reproduces exactly
the artifacts that were reviewed, or fails outright, and no sdist ever runs a `setup.py` on the
machine. `requirements/install.cmd` and `requirements/install.sh` are the entry points — run by a
person, deliberately; nothing in the build or any agent invokes them. See
[requirements/README.md](requirements/README.md) for the procedure.

## How verification is wired

**Dafny runs in-process.** `DafnyProgram` exposes `ParseAsync`, `ResolveAsync` and `VerifyAsync`,
each returning `Result<T>` carrying Dafny's own formatted diagnostics. `VerifyAsync` distinguishes
two failures that are easy to conflate: a `Failure` means the pipeline could not run — a syntax
error, a type error, no solver — whereas a `Success` whose `Verified` is false means it ran and the
proof did not go through.

**TLA+ is split.** SANY parses in-process, which is what a language server would want. TLC does not:
under IKVM every TLC run constructs an `FPSet`, which derives from `java.rmi.server.UnicastRemoteObject`,
and IKVM's RMI export check rejects `FPSetRMI.put` because it declares `java.io.IOException` rather
than `RemoteException` — legal on a real JVM, where `RemoteException` extends `IOException`. There is
no flag that avoids it, since the fingerprint set is on the mandatory path. `tlc2.TLC.main` also ends
in `System.exit`, which would take the host process with it.

So `TLCProcess` runs TLC on a real JVM with `-tool` and parses the result. That output is
machine-readable — `@!@!@STARTMSG code:severity @!@!@ … @!@!@ENDMSG code @!@!@` — and the parser is
built from the constants in the jar it is parsing: `MP.DELIM`/`STARTMSG`/`ENDMSG` for the framing,
`MP.ERROR`/`WARNING`/`STATE` for severities, and `tlc2.output.EC` for the 228 message codes. A
violation is therefore identified by code rather than by matching TLC's English, and a counterexample
comes back as `TLCRun.Trace`, one entry per state, instead of as scraped text. Because IKVM emits
those Java `static final` fields as C# `const`, they inline at compile time — reading them constructs
nothing and never touches the RMI machinery that makes in-process TLC impossible.

## License

Apache 2.0. See [LICENSE](LICENSE).
