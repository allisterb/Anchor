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
| **0** | a combinator from here — `all_complete`, `any_complete`, `none_failed`. A real Strands condition that *also* carries its TLA+ predicate. | nothing per workflow. One implementation, reviewed once, checked once by `tests/strands/condition_differential.py`. |
| **1** | `@condition_schema` on the user's own factory. The Python is untouched; the decorator stamps each closure it produces with the predicate the user asserts it means. | **a hole in every proof below it.** `translator.strands_graph_to_tla` lists it in the generated module's header rather than absorbing it. |
| **2** | no declaration | the edge is emitted as nondeterministic. Anything proved holds for every outcome of it — and a property that depends on one will not prove. |

Tier 1 is an assertion about the user's own Python, and Anchor does not verify it. It is named in
the output the way `DafnyProgram.AuditAsync` names an `{:extern}` assumption, for the same reason:
an assumption nobody can see is worse than one nobody has discharged.

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
