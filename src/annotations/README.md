# `annotations` — what an edge condition means

The only part of Anchor that goes **into a user's own code**.

A Strands `GraphEdge.condition` is an opaque Python callable. Before a conditional edge can be
modelled, something has to say what that callable means in the vocabulary `DependencyDAG.tla` is
stated over. Nothing can read it off the source — so it is declared, on the condition itself.

```python
from annotations import all_complete

builder.add_edge("review", "publish", condition=all_complete("review", "legal"))
```

## Three tiers, in descending order of how much is taken on trust

| tier | how the meaning is known | cost |
|---|---|---|
| **0** | a combinator from here — `all_complete`, `any_complete`, `none_failed`, `verdict`. A real Strands condition that *also* carries its TLA+ meaning. | nothing per workflow. One implementation, reviewed once, checked once by `tests/strands/condition_differential.py` (and `anchor_workflow.py` for `verdict`). |
| **1** | `@condition_schema` on the user's own factory. The Python is untouched; the decorator stamps each closure it produces with the predicate the user asserts it means. | **a hole in every proof below it.** `translator.strands_graph_to_tla` lists it in the generated module's header rather than absorbing it. |
| **2** | no declaration | the edge is emitted as nondeterministic. Anything proved holds for every outcome of it — and a property that depends on one will not prove. |

Tier 1 is an assertion about the user's own Python, and Anchor does not verify it. It is named in
the output the way `DafnyProgram.AuditAsync` names an `{:extern}` assumption, for the same reason:
an assumption nobody can see is worse than one nobody has discharged.

## `verdict` — a gate, and why it is not a failing node

```python
passed, rejected = verdict("preflight")
builder.add_edge("preflight", "score",  condition=passed)
builder.add_edge("preflight", "report", condition=rejected)
```

Strands' status vocabulary is `PENDING | EXECUTING | COMPLETED | FAILED | INTERRUPTED` and has **no
`REJECTED`**, so a gate's verdict has nowhere to live but the node's *result* — where the other
three combinators, which all read status, cannot see it. Reaching for `FAILED` instead is wrong
twice: a gate that rejects has worked rather than broken, and an `AgentBase` node can only reach
`FAILED` by raising, which fail-fasts the whole run.

**The pair comes back from one call**, and that is the entire declaration. What the gate will decide
stays unknown; what is declared is that the two edges are the *same* decision. Without it the models
give each edge its own free choice and explore both arms firing and neither — the two behaviours a
real gate cannot produce, and exactly the ones that broke `RunsAtMostOnce` and `NoSilentSkip` in
[`tests/strands/anchor_workflow.py`](../../tests/strands/anchor_workflow.py). The translator emits
declared pairs as `ExclusivePairs`, and each model's `Init` constrains one oracle to be the negation
of the other.

Wire only one arm and there is no exclusivity to declare, so the edge stays an ordinary free choice
and the generated header says so. That is not an error — a pipeline whose rejection goes nowhere is
a thing people write, and `NoSilentSkip` is left free to find it.

## Why the annotation rides on the object

A source comment above `add_edge(...)` binds by **line adjacency**. It is invisible to the runtime,
it detaches silently the moment the call moves into a loop or a helper, and reading it at all means
parsing the source — the thing this design exists to avoid.

`edge.condition` is the same object reference the scheduler calls, so annotating it binds by
**identity** and survives every refactoring.

## Where the line is

This declares meanings. [`translator`](../translator) reads them and reports what it was told; it
never decides. The split matters: a meaning is declared where the workflow is written, by whoever
wrote the condition.

## `graph_tla_value`, and why it is not `tla_value`

There is a `tla_value` in [`translator/emit.py`](../translator/emit.py) and it is **not the same
function**. That one escapes backslashes and quotes, because an entity reference carries its own
quotes — `Drupe::OAuthUser::"alice"` — and a naive `f'"{v}"'` closes the TLA+ literal early and the
module stops parsing. This one renders sets and tuples, and refuses a type it does not recognise
rather than guessing.

Each would be wrong in the other's place: the policy one cannot render a support set, and the graph
one would silently corrupt an entity reference. They carried the same name while they sat in
different trees; now that both are under `src/`, the name is the trap — it reads as a duplication
worth collapsing, and collapsing it breaks both. Hence the rename.
