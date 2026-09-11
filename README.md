# Anchor

Formal verification for the **deterministic envelope** around [Amazon Strands
SDK](https://strandsagents.com/) agents — dependency ordering, budgets, tool authorization, and
termination.

**It does not verify what a model decides.** Strands is a model-driven framework, and an agent's
choice of tools and task sequencing is the model's business. Anchor's subject is what can be
guaranteed *regardless* of what the model decides, which is why every spec here treats the model as
adversarial nondeterminism rather than trying to describe it.

Anchor models that envelope as a state machine that can be checked before it is run. TLA+ is used to
verify the protocol's logic — its safety and liveness — and Dafny to write the implementation
itself, which is then translated to Python on the Strands SDK. The goal is that, given the stated
assumptions hold, the generated code is provably well-behaved rather than merely tested.

Both humans and agents are meant to author these models, so the verifiers are exposed as a library
rather than as a wrapper around a command line.

An entry in the [Amazon Agents for Humans Hackathon](https://agentsforhumans.devpost.com).

## Status

Milestone 1 — confirm the Dafny and TLA+ toolchains work end to end — is complete.

| | Parse | Type check | Verify / model check | Audit | Translate |
|---|---|---|---|---|---|
| **Dafny** | in-process | in-process | in-process | in-process | Python, in-process |
| **TLA+** | in-process (SANY) | — | out-of-process (TLC) | — | — |

Milestone 2 — TLA+ models of real Strands workflows — is most of the way there. 43 tests, all green.

**A live Strands `Graph` is translated into a model, rather than described by one.** `GraphBuilder`
is a construction API, so the object *is* the workflow and the runtime executes that same object;
walking it is translation, not paraphrase. Nothing is hand-transcribed, so nothing can drift.

**The models found real behaviour in the SDK**, each confirmed by running it rather than by reading
it. See [Verifying a deterministic graph](#verifying-a-deterministic-graph).

**The Dafny → Python path runs end to end**: a verified workflow whose model is bound to a real
Python module via `{:extern}`, translated and executed against it. `DafnyProgram.AuditAsync`
enumerates the trust boundary that remains — every point where the proof rests on an assumption
rather than a proof — so it is a checked output rather than a paragraph someone maintains by hand.

**Every spec is paired with variants carrying one deliberate mistake each**, and the suite requires
those to fail. A verifier that only ever reports success proves nothing. [`specs/`](specs/) also
holds the case where the two tools stop overlapping: a race on a shared budget that TLC finds and no
Dafny loop invariant can express.

**Authorization policies are checked too, and this is where it generalises.** A policy constrains
what an agent *does* even when nothing constrains what it decides, so it applies to every
coordination pattern rather than one. [`specs/policy/TemporalPolicy`](specs/policy/TemporalPolicy) asks whether a
session-aware permit can ever grant anything — and whether a rule can be deleted, and whether an
edit changed a decision — AWS notes that temporal policies "do not currently
support the powerful automated reasoning analysis tools that Cedar provides" — and its reading of
those semantics is held against the reference implementation's own corpus — **786 recorded cases**,
covering every temporal operator including the `count`/`sum` aggregations.

## Which part of Strands this applies to

Strands is model-driven: *"modern models are sophisticated enough to be their own orchestrators."*
It offers four coordination patterns, and **only one of them is deterministic** —
[graphs](https://aws.amazon.com/blogs/opensource/strands-agents-and-the-model-driven-approach/),
recommended for *"business processes that require mandatory checkpoints or compliance
requirements"*. Anchor's coverage differs per pattern, and is worth stating precisely rather than
implying:

| Strands pattern | what Anchor covers |
|---|---|
| **Graphs** (deterministic) | dependency ordering, edge conditions, the executor's own loop. [`specs/strands/DependencyDAG`](specs/strands/DependencyDAG), [`specs/strands/StrandsGraph`](specs/strands/StrandsGraph) |
| **A single model-driven agent** | budget bounds and termination under a model free to fail forever. [`specs/foundations/BoundedRetry`](specs/foundations/BoundedRetry) |
| **Swarms / agents-as-tools** | concurrent agents sharing one budget. [`specs/foundations/SharedBudget`](specs/foundations/SharedBudget). Handoffs and shared context are **not** modelled |
| **Any agent that calls tools** | authorization decisions, differential-tested against the real Cedar engine. [`specs/policy/cedar`](specs/policy/cedar) |
| **Agents deployed behind AgentCore Gateway** | session-aware (Dogwood) policies: whether a permit can ever grant anything, whether a rule decides anything at all, whether an edit changed a decision, and whether a gate means what it reads like. [`specs/policy/TemporalPolicy`](specs/policy/TemporalPolicy) |
| **Meta agents** | nothing |

The niche is narrow, and deliberately so: verification pays where determinism is already demanded,
which is exactly the population Amazon points at graphs for.

## Verifying a deterministic graph

```bash
python tests/strands/graph_to_tla.py
```

The translator emits the graph; the properties live once, reviewed, in the specs that consume it. A
new workflow is checked against them without anyone rewriting anything.

Three behaviours it surfaced, none of which shows up in a passing test run:

| | |
|---|---|
| **Readiness is OR, not AND** | a node fires on the *first* incoming edge whose source completed. `GraphNode.dependencies` never gates execution. An unguarded join can start before all its parents are done — though only when those parents cannot share a batch, so the shape matters as much as the graph. |
| **A node can run twice** | readiness is recomputed per completed batch, and an earlier firing does not disqualify a later one. The agent is invoked twice: charged twice, output recomputed. |
| **A skipped node looks like success** | when nothing is ready the loop ends. A node whose conditions never pass is never run, never appears in `results`, and the graph reports `Status.COMPLETED`. Probed: 2 of 3 nodes run, no error, no warning. |

The first is documented by the SDK; the consequences of the other two are easy to miss. All three are
now checked, and the fix for the first two is a condition on the join — which Anchor supplies as a
combinator that carries its own TLA+ meaning, so nothing per-workflow has to be trusted.

**Two models, deliberately.** [`DependencyDAG`](specs/strands/DependencyDAG) is the orchestrator of
arXiv:2510.14133 — it cancels orphaned subgraphs and requires every task to terminate.
[`StrandsGraph`](specs/strands/StrandsGraph) is the executor Strands actually runs. They disagree in both
directions, and neither is a refinement of the other: `DependencyDAG` has no notion of a batch and so
reports violations the executor cannot produce, while `StrandsGraph` catches a whole failure class —
the run ending early with nodes unexecuted — that the paper's machine cannot express. The translator
runs both and prints the comparison alongside what the SDK actually did.

**What a condition means is checked, not asserted.** An edge condition is opaque Python, so it gets
one of three treatments: a reviewed combinator, a user-declared predicate that is
differential-tested against the real callable, or an explicit "not modelled" that is counted rather
than guessed at. See [docs/verifying-a-strands-graph.md](docs/verifying-a-strands-graph.md).

### What this does not establish

Worth stating plainly, because a framework like this invites overclaiming:

- **Nothing about what an agent says.** Agents appear only as completing or failing.
- **Nothing about the refinement gap.** A proof about a variable called `spent` says nothing about
  whether `spent` was computed from the right field — and reading the wrong one is a real,
  compounding overcharge that every proof here would still pass.
- **Nothing about a model-driven agent's choices** — which tool to call, what to do next, when
  it is finished. Three of Strands' four coordination patterns hand that to the model, and no
  spec here has an opinion about it.
- **Nothing about code paths outside the graph.**

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
| `tests/Anchor.Tests.Verifier` | tests for both verifiers, and for the Python harnesses below |
| `tests/strands/` | the graph translator and the differential tests, run against the real SDK |
| `specs/` | models of agent workflows, one directory per subject, all checked by the test suite |
| `docs/` | framework documentation; `docs/agent/` holds internal working notes — handoffs and task writeups |
| `requirements/` | dependency pins: `strands/` for Python (hash-locked), `dogwood/` for the Rust lockfile |
| `python/` | the Python venv the Strands SDK is installed into (gitignored) |
| `lib/` | native dependencies, fetched by the build scripts (gitignored) |
| `reference/` | third-party source read for reference, never built (gitignored) |

## Python

The Strands SDK is the target the Dafny workflows are translated to, and lives in a venv at
`python/`, separate from the .NET build and installed by hand rather than by the build scripts.

It is installed with pip in hash-checking mode and wheels-only: an install either reproduces exactly
the artifacts that were reviewed, or fails outright, and no sdist ever runs a `setup.py` on the
machine. `requirements/strands/install.cmd` and `requirements/strands/install.sh` are the entry points — run by a
person, deliberately; nothing in the build or any agent invokes them. See
[requirements/strands/README.md](requirements/strands/README.md) for the procedure.

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
