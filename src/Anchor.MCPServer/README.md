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

| tool | answers |
|---|---|
| `CheckPolicy` | is each rule load-bearing — VACUOUS, REDUNDANT, DEAD or live; `against` for a diff; `property` for a claim of your own |

The descriptions are written for the model that reads them rather than as API docs. Three things
they carry deliberately, because a verdict repeated without them is more confident than it deserves:

- **the bound is real** — VACUOUS means "no session of up to `attempts` attempts", not "never";
- **pass `eventSchema` whenever one exists** — without it every answer assumes the unpinned reading,
  and the shipped default partitions history by principal;
- **a refusal is not a pass** — a policy outside the modelled subset comes back with `Answered`
  false and a reason, which is a different thing from a policy with no findings.

## Tests

[`tests/Anchor.Tests.MCPServer`](../../tests/Anchor.Tests.MCPServer) runs the tool against the
command line it wraps and compares the output whole. Two ways to reach the same code is two chances
to get a different answer, and argument marshalling, path resolution and output parsing all sit in
between. `ProtocolTests` drives the whole thing with a real MCP client, which is the part an agent
host actually exercises.
