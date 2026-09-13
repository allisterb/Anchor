"""What a Strands edge condition *means*, declared on the condition itself.

A `GraphEdge.condition` is an opaque Python callable. Before a conditional edge can be modelled,
something has to say what that callable means in the vocabulary `DependencyDAG.tla` is stated over.
This is that something, and it is the only part of Anchor a user writes *into their own code*:

    tier 0  a combinator from here -- `all_complete("a", "b")` is a real Strands condition that
            also carries its TLA+ predicate. Meaning by CONSTRUCTION: one implementation, reviewed
            once, checked once by `tests/strands/condition_differential.py`. Nothing per-workflow
            is taken on trust. `verdict()` is the odd one: a gate's outcome is not a function of
            any node's STATUS, so what it declares is not a predicate but that its two edges are
            one decision -- see its docstring, and the README.
    tier 1  `@condition_schema` on a user's own factory. The Python is untouched; the decorator
            stamps each closure with the predicate the user asserts it means. That assertion is a
            HOLE in every proof that follows, and the translator lists it as one.
    tier 2  no declaration. The honest model is a nondeterministic edge, and nothing about what it
            decides is claimed.

THE ANNOTATION RIDES ON THE OBJECT, not on a source comment. `edge.condition` is the same object
reference the scheduler calls, so annotating it binds by identity and survives a refactoring that
moves the `add_edge` call into a loop or a helper. A comment above that call binds by line
adjacency: invisible to the runtime, silently detached the moment the code moves.

    from annotations import all_complete, condition_schema

`translator.strands_graph_to_tla` reads these; it does not define them. That split is the point --
the meaning is declared where the workflow is written, and the translator only reports what it was
told.
"""

from __future__ import annotations

from .conditions import (STATES, VERDICT_PASS, Branch, ConditionUse, all_complete, any_complete,
                         condition_schema, graph_tla_value, meaning, none_failed, verdict)

__all__ = [
    "STATES", "VERDICT_PASS", "Branch", "ConditionUse", "all_complete", "any_complete",
    "condition_schema", "graph_tla_value", "meaning", "none_failed", "verdict",
]
