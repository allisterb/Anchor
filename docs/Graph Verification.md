## Graph checks
## Status

Milestone 1 — confirm the Dafny and TLA+ toolchains work end to end — is complete.

| | Parse | Type check | Verify / model check | Audit | Translate |
|---|---|---|---|---|---|
| **Dafny** | in-process | in-process | in-process | in-process | Python, in-process |
| **TLA+** | in-process (SANY) | — | out-of-process (TLC) | — | — |

Milestone 2 — TLA+ models of real Strands workflows — is most of the way there. 79 tests, all
green. CI runs them on Linux; Windows is covered by running the suite locally.

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
coordination pattern rather than one — and it is the one part of this that ships as a tool you can
point at your own file. AWS notes that temporal policies "do not currently support the powerful
automated reasoning analysis tools that Cedar provides"; this answers three questions about one.
See [Checking an authorization policy](#checking-an-authorization-policy).

**The reading of Dogwood behind it is differential-tested against Dogwood**, on **911 (trace,
expected) pairs from 468 cases** of the reference implementation's own regression corpus, and
against the **built engine** on traces that corpus never recorded. Every operator is covered, each
mutation-checked against the wrong reading a reasonable implementation would have picked.

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

| `strands_graph_to_tla.py` | walks a **live** Strands `Graph` into `Workflow.tla` |

That last row is the second translation and the one that verifies Anchor itself. `GraphBuilder` is
the construction API, so the graph object **is** the workflow the runtime executes — walking it is
translation rather than inference. An edge condition is an opaque Python callable, and the
translator does not guess what one means: a combinator that carries its own TLA+ predicate is
meaning by construction, a user's declared assertion is emitted as a **hole listed in the generated
module's header** rather than absorbed silently, and an undeclared condition becomes a
nondeterministic edge about which nothing is claimed


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

