# `translator` — source artefacts to TLA+

Two things get translated here, and they exist for the same reason: **a model written by reading
something is a paraphrase, and nothing checks a paraphrase.** In both cases the artefact itself is
the input.

| | from | to |
|---|---|---|
| **policies** | Dogwood `.dw` text | the records `DogwoodSemantics!Decide` evaluates |
| **workflows** | a live Strands `Graph` | the definitions `DependencyDAG.tla` checks |

```
.dw text ──> parse ──> policy dicts ──> emit ──> TLA+ records ──┐
               ▲                                ▲               │
         schema (pins)                  trace (events)          ├──> tlc ──> a verdict
                                                                │
GraphBuilder ──> Graph ──> strands_graph_to_tla ──> Workflow.tla ┘
```

| | |
|---|---|
| `parse.py` | the recursive-descent parser for the modelled Dogwood subset, built against the real `.pest` grammar in the reference tree. Refuses anything outside the subset rather than guessing, and names the *feature* it refused rather than the token it tripped over. Macros are expanded here. |
| `schema.py` | reads an `event.dwschema` for the one thing in it that changes what a policy **means**: a `pin`, which forces a field of every event to equal something about the decision. A policy cannot see or bypass it. |
| `emit.py` | the TLA+ data. Every value is tagged with its kind so TLC refuses a cross-kind comparison instead of quietly answering one. |
| `trace.py` | reads an event log into trace records. `@N` is seconds. |
| `tlc.py` | finds the tools jar by glob, and runs TLC. |
| `strands_graph_to_tla.py` | walks a live Strands `Graph` into `Workflow.tla`. `GraphBuilder` is the construction API, so the graph **is** the workflow the runtime executes — walking it is translation, not inference. |
| `dw_to_tla.py` | the script: regenerates `specs/policy/TemporalPolicy/RotationPolicies.tla`. `--check` fails if it has drifted from the `.dw` sources. |

## What a graph translation refuses to pretend

An edge condition is an opaque Python callable, and `strands_graph_to_tla` does not guess what one
means. `meaning()` in [`annotations`](../annotations) decides that, and this module reports what it was told:

- **tier 0** — a combinator carrying its own TLA+ predicate. Meaning by construction.
- **tier 1** — a user's `@condition_schema` assertion. That is a **hole in every proof below it**,
  and it is listed in the generated module's header as one rather than absorbed.
- **tier 2** — no declaration, so the edge is emitted as nondeterministic and nothing about what it
  decides is claimed.

Those declarations live in [`annotations`](../annotations), which is the only part of Anchor that
goes into a user's own code. A meaning is declared where the workflow is written, by whoever wrote
the condition; this module reads it and never decides.

**It is deliberately not re-exported from `__init__.py`.** Importing it pulls in the Strands SDK;
importing a policy translator should not. `import translator` loads no `strands` module, and that
is worth keeping true.

## Why it is a package

It was not one, and the shape of the damage is worth recording because it is the ordinary way a
library fails to appear.

The parser and schema reader sat in `tests/strands/` next to the harnesses that exercised them,
every TLA+ emitter lived **inside `dogwood_differential.py`**, and `to_tla` lived inside a file
whose other 400 lines build fixture graphs. So `dw_to_tla.py`, whose output is a checked-in spec,
imported `tla_cond` from a test harness, and so did the vacuity checker. Nothing was wrong with the
code; the dependency arrow just pointed the wrong way, and would have kept pointing that way into
the MCP server.

Two duplications had already appeared, each character for character, which is what the missing layer
looked like from outside:

- `UNITS` — the second/minute/hour/day table — in both `dogwood_parse.py` and `dogwood_differential.py`.
- `policy_seq` — a policy list as a TLA+ sequence — in both `dw_to_tla.py` and `properties.py`.

A third was worse than a duplication. Five harnesses each spelled out the TLC command line, and the
`-Djava.io.tmpdir` flag that stops parallel runs corrupting each other's unpacked standard modules
was missing from **all five** — the C# runner had carried it for a while with a comment explaining
that it cost about one run in four. A copied command line is a command line that drifts. There is
now one `run_tlc`, and the explanation lives with it.

## The boundary

The library translates and runs. It does not decide what to check, and it does not decide what
follows from what it translated — that is [`checker`](../checker). Differential harnesses, corpus
walkers and fixture graphs are consumers and live in `tests/`.

The test for whether something belongs here is whether the MCP server would need it to answer a
question about an artefact it was handed.

**Nothing here imports from `tests/`.** If that ever reverses, it will show up in `__init__.py`
first.
