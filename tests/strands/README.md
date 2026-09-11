# Strands experiments

Implementations against the real SDK, for learning its surface. Nothing here is generated from a
spec — that is the point of the word *informal*. The verified artefacts live in
[`specs/`](../../specs).

**They are no longer hand-run only.** `HarnessTests.cs` in the test project runs all eight as part
of the suite, each asserting the finding it exists to pin. They **skip** rather than fail when what
they need is absent — the repo venv, which is the case in CI, and for `dogwood_replay.py` also the
built Dogwood binary. So the pins hold locally and not on GitHub.

```bash
python tests/strands/shared_budget.py
```

Needs the venv (`requirements/strands/install.cmd`), and nothing else — the model is scripted, so there is
no network call, no credentials, and no AWS.

| | |
|---|---|
| `shared_budget.py` | [`specs/foundations/SharedBudget/`](../../specs/foundations/SharedBudget) in Strands: several agents on one budget, with both the reserving ledger and the naive one. |
| `graph_to_tla.py` | translates a live Strands `Graph` into the TLA+ that [`specs/strands/DependencyDAG/`](../../specs/strands/DependencyDAG) checks. |
| `cedar_differential.py` | the Cedar model against the real engine. See [`specs/policy/cedar/`](../../specs/policy/cedar). |
| `condition_differential.py` | the edge-condition predicates in [`anchor_conditions.py`](../../specs/strands/DependencyDAG/anchor_conditions.py) against the Python callables they annotate. |
| `dogwood_differential.py` | our TLA+ reading of Dogwood's temporal operators against that language's own regression corpus — 654 pairs, one TLC run. See [`specs/policy/TemporalPolicy/`](../../specs/policy/TemporalPolicy). |
| `dogwood_replay.py` | the same reading against the **built** engine, on five traces the corpus never recorded — it contains no `::error` event at all, and that kind is what the `specs/policy/TemporalPolicy` finding rests on. The policies are checked in as `tests/policies/approval_gate_*.dw`; the traces are generated here. Needs the compiled binary; skips without it. |
| `vacuity.py` | **the tool**: point it at any `.dw` file and it model-checks every permit in it for vacuity, one TLC run each, reporting a witness session or a VACUOUS verdict. See [`specs/policy/TemporalPolicy/`](../../specs/policy/TemporalPolicy). |
| `dogwood_parse.py` | the recursive-descent parser for the modelled Dogwood subset. Refuses anything outside it rather than guessing. |
| `dw_to_tla.py` | translates a `.dw` policy file into the TLA+ data a spec checks, so a policy is model-checked as written rather than as paraphrased. `--check` fails if the generated module has drifted. |

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

Edges == {<<"analysis", "report">>, <<"factcheck", "report">>,
          <<"research", "analysis">>, <<"research", "factcheck">>}

\* No edge in this graph carries a condition, so every edge is unconditional and
\* readiness is Strands' OR default: one completed parent is enough.
EdgeCond(from, to, st) == TRUE

EdgeSupport(from, to) == {}
```

The emitted graph is `Edges`, not a `Deps` AND-set, and that is the whole finding below.
`DependencyDAG.tla` derives the parent set HP10 quantifies over from `Edges` itself, so the graph
and the thing the property is stated over cannot disagree.

## Strands readiness is per-edge, and OR by default

An earlier version of this translator emitted `GraphNode.dependencies` as `Deps[t]` and the spec
gated execution on every parent being complete. **That is not what the SDK does.**
`Graph._is_node_ready_with_conditions` returns `True` on the *first* incoming edge whose source is
in the completed batch and whose condition passes; `dependencies` is used only to find entry points
and to gather node inputs, and never gates execution. The SDK documentation says so plainly:

> In Python, the default behavior is OR semantics — a target node fires when **any** incoming edge's
> source completes. Use conditional edges to explicitly wait for all dependencies.

Modelling it as AND described a stricter orchestrator than the one that runs, which is the unsound
direction — HP10 verified against a discipline nothing enforces. The diamond above hides it, because
`analysis` and `factcheck` execute in one batch and `report` sees both complete. A shape whose
parents cannot share a batch does not hide it:

```
A ──> B ──> C
└───────────^
```

Against the real SDK, `execution_order` contains **C twice** — admitted once on the `A` edge while
`B` is still running, and again when `B` completes. Under AND semantics C would run exactly once.
TLC finds the matching counterexample:

```
state = [A |-> "COMPLETED", B |-> "BLOCKED", C |-> "IN_PROGRESS"]
```

### `DependencyDAG.tla` over-approximates, and the diamond is where it shows

TLC reports HP10 violated on the **diamond** too — but the real executor cannot produce that, and an
earlier version of this file wrongly said the SDK predicted it.

`DependencyDAG.tla` has no notion of a batch: it interleaves tasks individually, so it admits
`report` with one parent done. Strands seeds `analysis` and `factcheck` into one batch,
`_execute_nodes_parallel` awaits all of it, and readiness is recomputed only afterwards. Probed 3/3:

```
docs diamond  ['research', 'analysis', 'factcheck', 'report']   report ran 1x
skew          ['A', 'B', 'C', 'C']                              C ran 2x
```

So read its two outcomes asymmetrically:

| | |
|---|---|
| **holds** in `DependencyDAG` | holds in reality. Over-approximation is sound in this direction. |
| **VIOLATED** in `DependencyDAG` | *may* be spurious — as it is for the diamond. Confirm against [`specs/strands/StrandsGraph/`](../../specs/strands/StrandsGraph), which models the batch loop, or against the SDK. |

The skew violation is real in both models and in the SDK. The diamond's is an artifact.

**What `DependencyDAG.tla` does not cover.** Batching, per the above; and `COMPLETED` is terminal
there, so the *second* run of C is outside it. Both are the same OR rule showing up again, and both
are modelled in [`specs/strands/StrandsGraph/`](../../specs/strands/StrandsGraph).

## Conditions that carry their own meaning

The remedy for the above is a condition on the join — `all_dependencies_complete([...])`, the
factory the Strands docs tell every user to hand-write.
[`specs/strands/DependencyDAG/anchor_conditions.py`](../../specs/strands/DependencyDAG/anchor_conditions.py) ships
it as a combinator that is simultaneously a real Strands condition and its own TLA+ predicate:

```python
builder.add_edge("analysis", "report", condition=all_complete("analysis", "factcheck"))
```

which `graph_to_tla.py` reads straight off the edge object:

```tla
EdgeCond(from, to, st) ==
    CASE <<from, to>> = <<"analysis", "report">>  -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] <<from, to>> = <<"factcheck", "report">> -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] OTHER                                    -> TRUE
```

**The annotation rides on the condition object, not on a source comment.** A comment above
`add_edge(...)` binds by line adjacency — invisible to the runtime, silently detached when the call
moves into a loop or a helper, and readable only by parsing the source, which is the thing being
avoided. `edge.condition` is the same reference the scheduler calls, so annotating it binds by
identity. `@condition_schema` wraps a *factory* for the same reason: in the docs pattern the
arguments, not the function, are what differ per edge, so the wrapper stamps the bound arguments
onto each closure the factory returns.

`graph_to_tla.py` runs both graphs both ways, and the SDK agrees with TLC on each:

| | real SDK | TLC |
|---|---|---|
| unguarded | C admitted twice | HP10 **VIOLATED** |
| guarded with `all_complete` | C admitted once | HP10 holds |

## Conditions with no meaning to declare

Some conditions cannot be given a predicate over the spec's vocabulary at all, because they read
things the spec does not hold — the agent's output text, or the `invocation_state` dict:

```python
def approved(state) -> bool:
    return "approve" in str(state.results["plan"].result).lower()
```

These are **not modelled**, and the model says so. `NondetEdges` lists them, and `oracle` — a free
choice fixed for each behaviour — stands in for whatever they decide. TLC runs the workflow once per
combination, so anything that verifies holds *whatever the conditions decide*, with nothing about
them translated and therefore nothing to mistranslate.

The trade is precision, and both halves of it are worth seeing:

```
routing on an opaque condition -- one parent per target
  assumed predicates: 0    not modelled: 2
  HP10 + termination: HOLD

the same opacity on a join
  assumed predicates: 0    not modelled: 2
  HP10 + termination: VIOLATED
      /\ state = [a |-> "BLOCKED", b |-> "COMPLETED", z |-> "IN_PROGRESS"]
      /\ oracle = (<<"a", "z">> :> FALSE @@ <<"b", "z">> :> TRUE)
```

Routing verifies: each target has one parent, so an edge can only fire once that parent completed,
which is HP10 no matter what the condition says. The join does not, and the counterexample names the
combination — `b`'s edge fired alone. Tier 2 cannot clear that; declaring the condition can.

**The abstraction is "unknown but fixed", and that is a real limit.** A condition whose answer
changes as the run progresses is not covered, because `oracle` cannot flip mid-behaviour. Fixing it
per behaviour is what lets the model recognise an edge that will never fire, which is what lets an
orphaned task be cancelled rather than waiting forever. A time-varying condition needs a real
predicate, not this.

## Strands skips what it cannot admit, and calls it success

Worth knowing before reading `AllTerminate` as a statement about the runtime:

```
real SDK: status=Status.COMPLETED, ran ['plan', 'reject'], 2/3 nodes, skipped ['approve']
```

When no node is ready the execution loop simply ends. A node whose conditions never pass is never
run, never appears in `results`, and the graph reports `COMPLETED`. There is no hang and no error —
a workflow can drop part of its graph and still look successful. The model has no such state:
`AllTerminate` is a property of the model, not a claim about Strands.

## Checking the annotation, rather than trusting it

An annotation is only better than a hand-written translator if its claim is checked — otherwise it
is the same silent-disagreement trap with a nicer syntax. `condition_differential.py` enumerates
every assignment of task states over a condition's declared support, asks the real callable for a
verdict on each, and has TLC compare that table against the predicate:

```
Tier 0 -- combinators, whose meaning is construction rather than assertion
  all_complete("a", "b")                       36 states  combinator AGREE
  any_complete("a", "b")                       36 states  combinator AGREE
  none_failed("a", "b")                        36 states  combinator AGREE
  all_complete("a", "b", "c")                 216 states  combinator AGREE

Tier 1 -- a user's own factory, with an asserted meaning
  all_dependencies_complete(["a", "b"])        36 states  assumed    AGREE

Mutation -- the same callable with a deliberately wrong predicate
  mistranslated(["a", "b"])                    36 states  assumed    DISAGREE
```

The mutation is there because a harness that cannot catch `\E` where the callable means `\A` is
checking nothing, and every AGREE above would be worthless.

**The state vocabularies differ, and that mapping is under test too.** The spec has six states, the
SDK five, sharing only `COMPLETED` and `FAILED` — and a condition sees neither directly, because it
reads `state.results`, which gains an entry only once a node finishes. So `BLOCKED`, `READY`,
`IN_PROGRESS` and `CANCELED` all reach a condition as an absent result, and the predicate has to
agree with that or fail here.

**An understated support set is caught too.** `EdgeSupport` tells `DependencyDAG.tla` when a false
condition can no longer become true; naming too few tasks would let the model cancel a live one. A
predicate that reads outside its declared support indexes `st` outside its domain, and TLC says so
by name — checked, not assumed:

```
Error: Attempted to apply function:
to argument "b", which is not in the domain of the function.
```

**Scope.** The oracle populates `NodeResult.status` and nothing else, so a condition reading result
*content* or the `invocation_state` dict is out of scope by construction — and those are exactly the
conditions that cannot be given a predicate over the spec's vocabulary either. They belong in tier 2.

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
