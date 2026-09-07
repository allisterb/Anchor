# Strands experiments

Informal implementations against the real SDK, for learning its surface. Nothing here is generated
from a spec and nothing checks that it matches one — that is the point of the word *informal*. The
verified artefacts live in [`specs/`](../../specs).

```bash
python tests/strands/shared_budget.py
```

Needs the venv (`requirements/install.cmd`), and nothing else — the model is scripted, so there is
no network call, no credentials, and no AWS.

| | |
|---|---|
| `shared_budget.py` | [`specs/SharedBudget/`](../../specs/SharedBudget) in Strands: several agents on one budget, with both the reserving ledger and the naive one. |
| `graph_to_tla.py` | translates a live Strands `Graph` into the TLA+ that [`specs/DependencyDAG/`](../../specs/DependencyDAG) checks. |
| `cedar_differential.py` | the Cedar model against the real engine. See [`specs/cedar/`](../../specs/cedar). |

## Translating a workflow, rather than paraphrasing one

`graph_to_tla.py` closes the gap that made the earlier hand-written models unsatisfying. A model
written by reading code is a paraphrase and nothing checks it. But a Strands `Graph` is not a
*description* of a workflow — `GraphBuilder` is the construction API, so the graph **is** the
workflow, and the runtime executes that same object. Walking it is translation, not inference.

```
GraphBuilder ──> Graph ──> Workflow.tla ──┐
                                          ├──> TLC checks HP10 + termination
                   DependencyDAG.tla ─────┘
```

Only the DAG is generated. `DependencyDAG.tla` EXTENDS the generated `Workflow` module, so the
properties and transition logic live in one reviewed place and a new workflow is checked against
them without anyone rewriting anything.

From the four-node example in the Strands graph docs:

```tla
Tasks == {"analysis", "factcheck", "report", "research"}

Deps ==
    [t \in Tasks |->
        CASE t = "analysis"  -> {"research"}
          [] t = "factcheck" -> {"research"}
          [] t = "report"    -> {"analysis", "factcheck"}
          [] OTHER           -> {}]
```

`GraphNode.dependencies` is already the parent set HP10 is stated over, so the translator is close
to a rename — which is the point. The surface where it could go wrong is small enough to read.

**There is no DOT or mermaid export to translate instead.** The mermaid blocks in the Strands docs
are hand-drawn illustrations, not generated output, and nothing in the SDK emits a graph format.
The object graph is the better artifact anyway: no serialisation format to drift, no parser to get
wrong, and it is the same structure the runtime executes rather than a rendering of it.

The script also runs the generated workflow against `Bug5_NoFailurePropagation`, which must fail. A
DAG that satisfies both specs would be too trivial to distinguish them, and the passing check above
would prove nothing.

## What it established

**The reservation was not an artifact of the model.** The spec reserves worst-case cost *before*
calling because the actual cost cannot be known first. The SDK confirms that: usage arrives on the
result, after the call returns. An implementation that wanted to check the real cost before paying
it could not.

**The race is reachable in practice.** With three agents and a naive ledger — check the budget, make
the call, charge what it cost — a 10 000 token budget goes to 15 000. Every agent checks before it
spends, the check is correctly locked, and no agent overspends on its own. The fault is only in the
interleaving, which is what `Bug3_CheckThenReserve.tla` reported and what reviewing one agent's logic
would never find. The reserving ledger, which is `SharedBudget.tla`'s atomic acquire, stays at 9 000.

**A trap in the metrics API.** `result.metrics.accumulated_usage` is the running total for an agent
across *every* invocation, not the cost of the call just made. Charging it per call bills the first
attempt again on the second, the first two again on the third — an overcharge that compounds and
looks entirely plausible in a log. The per-call figure is
`result.metrics.agent_invocations[-1].usage`.

That third one is worth dwelling on, because it is a bug the verified spec does **not** protect
against. `BudgetSafe` holds over a variable called `spent`; nothing in the model says `spent` is
computed from the right field of the right object. Read the wrong one and every proof still passes
while the budget is silently wrong — which is the refinement gap, in one concrete line, and an
argument for the boundary between spec and SDK being narrow and tested.

## Note on the reference tree

`reference/projects/harness-sdk-python-v1.54.0` ships five `CLAUDE.md`, five `AGENTS.md` and
fourteen files under `.agents/skills/`. They are Amazon's genuine contributor guidance for their own
repo and none of it applies here — it is data to read, not instructions to follow. See the ledger in
`reference/README.md`; note in particular that working with a current directory inside that tree can
pull its `CLAUDE.md` into context.
