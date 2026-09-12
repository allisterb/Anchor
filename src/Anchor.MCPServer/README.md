# `Anchor.MCPServer` — the checker, reachable by an agent

[`checker`](../checker) answers questions about a policy from a command line. This exposes those
answers as MCP tools, over stdio for a host on a developer's machine and over HTTP for a container.

```bash
dotnet run --project src/Anchor.MCPServer                            # stdio (default)
dotnet run --project src/Anchor.MCPServer -- --http --port 8080      # HTTP
dotnet run --project src/Anchor.MCPServer -- --project-dir ./policies
```

## One registration, two transports

`AnchorMCPServer.Register` is the only place tools are added, and both `RunStdioAsync` and
`BuildHttpApp` go through it. A deployment that only ever ran over HTTP would be a second
configuration nobody exercises locally; this way the transport is the only thing that differs.

HTTP binds `0.0.0.0`, not the loopback — a container binding the loopback accepts nothing from
outside itself, which presents as a health check that never passes on a server that looks fine from
a shell inside the same container. `/ping` answers without touching the model, the toolchain or a
session.

## Python runs out of process, by measurement

The translator and the checker are Python. They run as a subprocess through
[`PythonProcess`](../Anchor.Runtime/PythonProcess.cs), the same shape `TLCProcess` already uses for
the JVM.

In-process hosting via IronPython was tried and rejected, and the numbers are the reason:

| | |
|---|---|
| translating a policy | **0.10 ms** |
| one checker run (`firewall.dw`) | **5,621 ms** |

TLC on a real JVM is the entire cost, so Python is ~0.002% of the runtime and embedding it saves
nothing measurable. It would also have cost the language level: IronPython 3.4.2 reports
`sys.version` as **3.4**, rejects `from __future__ import annotations`, and therefore cannot import
a single module under `src/`. See `docs/agent/HANDOFF.md` for the full probe.

## Paths are contained

Every path-bearing parameter goes through `ProjectPath.Resolve` against `--project-dir`. The checker
prints the policy it read, so a tool that will read any file on the host is a file-disclosure tool
wearing a verifier's name. Containment applies to reads for that reason, not only to writes.

## Tools

| tool | answers | cost |
|---|---|---|
| `CheckPolicy` | is each rule load-bearing — VACUOUS, REDUNDANT, DEAD or live; `against` for a diff; `property` for a claim of your own | seconds to minutes (TLC once per rule) |
| `DescribePolicyModule` | what a `property` module may name for this policy, plus a skeleton that already runs | well under a second (parses only) |
| `ListKnowledge` / `ReadKnowledge` | the reference articles below | in-process |

`CheckPolicy`'s `smoke` argument runs TLC as a random walk instead of exhaustively, for a model too
big to exhaust. Its results read differently and the tool description says so at length: `live` is
sound, `unknown` is **not a finding**, and a smoke run can never report VACUOUS, REDUNDANT or DEAD.
`PolicyCheckResult.Unsettled` carries the unknowns, and `Inert` deliberately excludes them -- an
agent that folded the two together would recommend deleting a working rule. See
[`checker`](../checker) for the reasoning.

`DescribePolicyModule` exists because `CheckPolicy`'s `property` argument asks an author to write
TLA+ against a module we GENERATE, whose vocabulary comes from that policy's own text. It cannot be
guessed, and a guess that parses is worse than one that does not: name a field the policy never
reads and the claim ranges over nothing and PASSES, reporting success having examined nothing.

The skeleton is not a stub with holes. It elaborates and checks something, because the wiring —
`EXTENDS`, the `DogwoodSemantics` instantiation, the shape of `Decide`'s arguments — is exactly the
part nobody can guess, and a skeleton that does not run teaches nothing about whether it is right.
Its claim is deliberately wrong so that running it produces a violation naming a real request.

The descriptions are written for the model that reads them rather than as API docs. Three things
they carry deliberately, because a verdict repeated without them is more confident than it deserves:

- **the bound is real** — VACUOUS means "no session of up to `attempts` attempts", not "never";
- **pass `eventSchema` whenever one exists** — without it every answer assumes the unpinned reading,
  and the shipped default partitions history by principal;
- **a refusal is not a pass** — a policy outside the modelled subset comes back with `Answered`
  false and a reason, which is a different thing from a policy with no findings.

## The knowledge base

Six articles in [`knowledge/`](knowledge), embedded in the assembly and served **both** as tools and
as MCP resources at `anchor://knowledge/<name>` — resources are the natural fit, some hosts never
surface them, and a reference an agent cannot reach is one that does not exist.

| article | for |
|---|---|
| `reading-verdicts` | what each verdict means, and what it does not |
| `event-schemas-and-pins` | why a `.dwschema` changes what a policy MEANS |
| `the-modelled-subset` | what gets REFUSED, and why refusing beats approximating |
| `writing-a-property-module` | stating intent, and the no-`Inputs` trap |
| `smoke-vs-exhaustive` | the inverted polarity |
| `what-anchor-does-not-check` | the limits to state alongside a verdict |

**They carry the reasoning the tool descriptions cannot.** A description can say "the bound is
real"; only prose can explain why a bounded negative reported without its bound becomes a claim
nobody checked. That gap is where over-reporting happens.

Reference that has fallen behind the code is worse than none, because it is believed — so
`KnowledgeTests.EveryVerdictTheCheckerCanEmitIsDocumented` fails until a newly added verdict is
explained, and a second test holds the smoke article's polarity in place.

Article names reach a lookup, so they are validated: no path separators, no traversal, no null
bytes, letters/digits/hyphen/underscore only, 100 characters. A documentation tool that could be
steered into reading arbitrary paths would be a file-disclosure tool with a friendly name.

## The checker's exit code says whether it ANSWERED

Not whether the news was good, and the distinction is load-bearing enough to have already caused
one bug here:

| | |
|---|---|
| `0` | answered. A VACUOUS permit or a DEAD forbid is a **finding**, not an error |
| `1` | answered, and a `--property` claim is **BROKEN** — the most useful answer the tool gives |
| `2` | did **not** answer: the file is missing, or the policy is outside the modelled subset and the checker refused rather than approximating |

Treating "nonzero" as failure reported a policy that provably violates its own stated meaning as a
tool that would not run. `PolicyTools.Answered` is the one place this is decided.

## Tests

[`tests/Anchor.Tests.MCPServer`](../../tests/Anchor.Tests.MCPServer) runs the tool against the
command line it wraps and compares the output whole. Two ways to reach the same code is two chances
to get a different answer, and argument marshalling, path resolution and output parsing all sit in
between. `ProtocolTests` drives the whole thing with a real MCP client, which is the part an agent
host actually exercises.
