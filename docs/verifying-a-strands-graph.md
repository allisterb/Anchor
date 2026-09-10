# Verifying a Strands graph with Anchor

You have a Strands **`Graph`** — the deterministic multi-agent primitive — and you want to know
whether it will misbehave. This is the procedure, what each step actually establishes, and — the
part that matters most — what it does not.

Everything stated here is checked by the test suite. Where a claim came from probing the real SDK
rather than from reading its source, it says so.

## Scope: this is about graphs, and graphs are the exception

Strands is a **model-driven** framework. Its position is that *"modern models are sophisticated
enough to be their own orchestrators"*, and it offers four coordination patterns —
agents-as-tools, swarms, graphs, and meta agents. Three of those hand sequencing to the model.

`Graph` is the deliberate exception: deterministic execution along predefined paths, which Amazon
recommends for *"business processes that require mandatory checkpoints or compliance requirements"*
and where *"audit trails require specific step-by-step documentation."*

**This document covers that primitive only.** Nothing here verifies a model-driven agent's choice of
tools or its task sequencing — those are the model's decisions, and no spec in this repo has an
opinion about them. What Anchor covers elsewhere in Strands, and what it does not, is in the
[root README](../README.md#which-part-of-strands-this-applies-to).

That narrowness is not incidental to the value. Verification pays where determinism is already
demanded, which is exactly the population Amazon points at `Graph` for.

---

## What Anchor gives you

| | |
|---|---|
| **A model of your graph, not a paraphrase of it** | `GraphBuilder` is a construction API, so the `Graph` object *is* the workflow. Walking it is translation. |
| **Two models to check it against** | one for the orchestration properties in the literature, one for the executor Strands actually runs. They disagree, usefully. |
| **A vocabulary for edge conditions** | so a conditional edge means something checkable instead of being opaque Python. |
| **An explicit list of what is still assumed** | counted, not buried. |

## What it does not give you

Say these out loud before claiming a workflow is verified.

- **Nothing about what an agent says.** Agents appear only as *completed* or *failed*. Output
  quality, hallucination, tool misuse — all outside every model here.
- **Nothing about the refinement gap.** A proof about a variable called `spent` says nothing about
  whether `spent` is computed from the right field. See the metrics trap below; it is real, it
  compounds, and no spec here catches it.
- **Nothing about code paths outside the graph.** A workflow that calls a model somewhere the state
  machine does not describe is not covered.

---

## Step 1 — translate the graph

```bash
python tests/strands/graph_to_tla.py
```

For your own graph, `to_tla(graph)` emits five definitions into a `Workflow.tla`:

| | |
|---|---|
| `Tasks` | the nodes |
| `Edges` | `<<from, to>>` pairs. The parent set is *derived* from this, so the graph and the properties cannot disagree. |
| `EdgeCond(from, to, st)` | what each condition means, where that is known |
| `EdgeSupport(from, to)` | which tasks a condition reads |
| `NondetEdges` | conditions with no declared meaning |

You get back a `Translation` carrying the emitted text plus two tallies — `assumptions` (things a
user asserted) and `nondet` (things nobody modelled). **Both are holes. Read them.**

---

## Step 2 — read the result, and know which model said it

Anchor checks your graph against two specs. They model **different orchestrators**, and neither is a
refinement of the other.

| | models | use it to ask |
|---|---|---|
| [`DependencyDAG`](../specs/DependencyDAG) | the Host Agent of arXiv:2510.14133 — cancels orphaned subgraphs, requires every task to terminate | do the published orchestration properties hold? |
| [`StrandsGraph`](../specs/StrandsGraph) | the executor Strands runs — batch, await, recompute readiness, fail fast, stop | what will my workflow actually do? |

`graph_to_tla.py` runs both and prints the comparison:

```
  graph                      DependencyDAG   StrandsGraph   the SDK
  docs diamond, unguarded    VIOLATED        HOLD           report ran 1x, after both parents (3/3)
  skew, unguarded            VIOLATED        VIOLATED       C ran 2x
  router, opaque conditions  HOLD            VIOLATED       COMPLETED having run 2/3 nodes
```

**Read a `DependencyDAG` violation as "worth checking", not as "your workflow is broken."** That
model interleaves tasks individually and has no notion of a batch, so it admits behaviours the
executor cannot produce. It **over-approximates**:

- *holds* there ⟹ holds in reality. Sound.
- *VIOLATED* there ⟹ **may be spurious.** Confirm against `StrandsGraph`, or against the SDK.

And the reverse trap: `DependencyDAG` reporting HOLD does not clear your workflow either, because
its orchestrator cancels what it cannot admit. Strands does not. A whole failure class — the run
ending early with nodes never executed — cannot be expressed in that machine at all.

---

## Step 3 — give your conditions a meaning

A `GraphEdge.condition` is opaque Python. There are three tiers, in descending order of how much is
taken on trust.

### Tier 0 — use a combinator

```python
from anchor_conditions import all_complete

builder.add_edge("analysis", "report", condition=all_complete("analysis", "factcheck"))
```

`all_complete`, `any_complete`, `none_failed` are real Strands conditions that carry their own TLA+
predicate. Meaning is construction, not assertion: reviewed once, differentially tested once,
nothing per-workflow to trust. **Prefer this wherever a case fits.**

### Tier 1 — declare your own

```python
@condition_schema("AllComplete",
                  tla='\\A n \\in {required_nodes} : st[n] = "COMPLETED"',
                  support=("required_nodes",))
def all_dependencies_complete(required_nodes):
    def check(state): ...
    return check
```

Decorate the **factory**, not the function — in the pattern the Strands docs use, the arguments are
what differ per edge. Your Python is untouched; the wrapper stamps each closure with the predicate
and the arguments it was built from.

**The predicate is your assertion, and Anchor does not verify it.** It is emitted into the generated
module as an `ASSUMED` block and counted. Check it:

```bash
python tests/strands/condition_differential.py
```

which enumerates every assignment of task states over the declared support, asks the real callable,
and has TLC compare.

### Tier 2 — don't declare it

Some conditions genuinely cannot be given a predicate, because they read what the model does not
hold:

```python
def approved(state) -> bool:
    return "approve" in str(state.results["plan"].result).lower()
```

These land in `NondetEdges` and are modelled as an unknown-but-fixed choice. Anything that verifies
holds *whatever they decide* — nothing translated, so nothing to mistranslate. The cost is
precision: a property that depends on what the condition does will not prove.

**Do not fake a predicate to get out of tier 2.** A condition reading result text or
`invocation_state` belongs there.

### Which tier

| your condition | tier |
|---|---|
| waits for some set of nodes to complete / not fail | **0** — use the combinator |
| a rule over node status that no combinator covers | **1** — declare it, then differential-test it |
| reads agent output, `invocation_state`, a clock, anything external | **2** — leave it undeclared |

---

## The failure catalogue

What actually goes wrong in Strands graphs. Each of these is checked, and each was confirmed against
the running SDK.

### 1. Readiness is OR, not AND

`_is_node_ready_with_conditions` returns `True` on the **first** incoming edge whose source is in
the completed batch and whose condition passes. `GraphNode.dependencies` is used only to find entry
points and gather inputs — **it never gates execution.** The SDK docs say so:

> In Python, the default behavior is OR semantics — a target node fires when **any** incoming edge's
> source completes. Use conditional edges to explicitly wait for all dependencies.

**The shape decides whether this bites.** Parents in the same batch complete together, so a plain
diamond is safe. Parents a batch apart are not:

```
A ──> B ──> C          C is admitted on the A edge while B is still running
└───────────^
```

*Fix:* `all_complete(...)` on every incoming edge of the join.

### 2. A node can run twice

Readiness is recomputed per completed batch, from edges out of *that* batch. An earlier firing does
not disqualify a later one. On the shape above, `execution_order` contains **C twice** — probed.

That means the agent is invoked twice: **charged twice**, and its output recomputed. The same guard
fixes it; guarded, C runs once.

### 3. A skipped node looks like success

When nothing is ready the loop simply ends. A node whose conditions never pass is never run, never
appears in `results`, and the graph reports `Status.COMPLETED`. Probed:

```
status=Status.COMPLETED, ran ['plan', 'reject'], 2/3 nodes, skipped ['approve']
```

No hang, no error, no warning. **A workflow can silently drop part of its graph and still look
successful.** `StrandsGraph`'s `NoSilentSkip` is the check; `DependencyDAG` cannot express it.

### 4. There is no cancellation

The SDK's `Status` has no `CANCELED`, and a node failure fail-fasts the entire run rather than
cancelling the subgraph beneath it. If you are reasoning from the paper's orchestrator, this is the
assumption that does not hold.

### 5. Shared budget is a race, not a check

Several agents each running individually-correct budget logic still overspend, because the check and
the reservation are two steps. A 10 000-token budget goes to **15 000** with three agents. Reserve
worst-case cost *before* the call — usage only arrives on the result, so checking the real cost
first is impossible. See [`specs/SharedBudget`](../specs/SharedBudget).

### 6. The metrics trap

`result.metrics.accumulated_usage` is the running total across an agent's invocations, **not** the
cost of the last call. Charging it per call bills the first attempt again on the second, and the
first two again on the third — an overcharge that compounds and looks entirely plausible in a log.

The per-call figure is `result.metrics.agent_invocations[-1].usage`.

**No spec here catches this**, and that is the point: `BudgetSafe` holds over a variable called
`spent`, and nothing says `spent` is computed from the right field. Read the wrong one and every
proof still passes while the budget is silently wrong.

---

## Reading a counterexample

TLC prints the state at each step. What to look at:

- **Which invariant.** `Error: Invariant HP10 is violated` names the property, and each property in
  these specs has one job.
- **The last state.** That is where it broke. `graph_to_tla.py` prints it for you.
- **The `oracle` value**, if the graph has tier-2 edges. It names the *combination of condition
  outcomes* that broke the property — `(<<"a","z">> :> FALSE @@ <<"b","z">> :> TRUE)` means `b`'s
  edge fired alone.
- **Whether it is a lasso.** A trace ending in `Back to state` is an infinite cycle — a liveness
  failure, not a path to a bad state.

**Do not assert on a specific counterexample** when writing a test around one. TLC reports whichever
it reaches first; describe the shape instead.

---

## What "verified" is allowed to mean

After all of the above, the honest claim is:

> Given that the declared condition predicates match their Python, that the SDK behaves as the
> executor model says, and that the listed assumptions hold, this workflow does not violate
> *these* properties.

Three qualifiers, none removable. The first is testable and should be tested. The second is what
`StrandsGraph` exists to keep honest. The third is printed by the translator every run, so it cannot
quietly grow.

Anything stronger than that is overclaiming.
