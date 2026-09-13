"""Strands edge conditions that carry their own TLA+ meaning.

A `GraphEdge.condition` is an opaque Python callable. To model a conditional edge, something has to
say what that callable *means* in the vocabulary DependencyDAG.tla is stated over — and there are
three ways to get that, in descending order of how much has to be taken on trust.

  tier 0  A combinator from this module. `all_complete("a", "b")` returns a real Strands condition
          that also carries its TLA+ predicate. The meaning is construction rather than assertion:
          one implementation, reviewed once, and checked once by
          tests/strands/condition_differential.py. Nothing per-workflow is trusted.

  tier 1  `@condition_schema` on a user's own condition factory. The Python is untouched; the
          decorator stamps each closure the factory produces with the predicate the user asserts it
          means, capturing the per-call-site arguments. That assertion IS a hole in the proof, and
          graph_to_tla.py lists and counts it the way DafnyProgram.AuditAsync lists {:extern}
          assumptions. It is checkable by the same differential harness, and should be checked.

  tier 2  No declaration at all. The honest model is a nondeterministic edge. Not implemented yet;
          graph_to_tla.py refuses such a graph rather than guessing.

WHY THE ANNOTATION RIDES ON THE OBJECT. A source comment above `add_edge(...)` binds by line
adjacency: it is invisible to the runtime, it detaches silently when the call moves into a loop or a
helper, and reading it at all requires parsing the source — the thing this design exists to avoid.
`edge.condition` is the same object reference the scheduler calls, so annotating it binds by
identity and survives every refactoring.

THE STATE VOCABULARIES DO NOT MATCH, AND THE MAPPING IS PART OF WHAT IS UNDER TEST.

    spec States   BLOCKED  READY  IN_PROGRESS  COMPLETED  FAILED  CANCELED
    SDK Status    PENDING  EXECUTING  COMPLETED  FAILED  INTERRUPTED

A condition sees neither directly: it reads `state.results`, which is populated only once a node
finishes. So every spec state except COMPLETED and FAILED appears to a condition as an absent
result. The predicates below are written to that, and the differential harness enumerates all six
spec states per node so the mapping is exercised rather than assumed.

Note the SDK has no CANCELED. Strands does not cancel an orphaned subgraph — it fails the whole run
fast — so `CancelOrphan` in the model has no counterpart in the runtime. That is a separate finding
from this file's concern; see docs/agent/HANDOFF.md.
"""

from __future__ import annotations

import functools
import inspect
import re
import string
from dataclasses import dataclass

from strands.multiagent.base import Status

# The state vocabulary DependencyDAG.tla is written over.
STATES = ("BLOCKED", "READY", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELED")


@dataclass(frozen=True)
class ConditionUse:
    """What one conditional edge means, stamped onto the condition object itself.

    Attributes:
        schema:  the combinator or schema name, for the assumption listing.
        tla:     the predicate, already substituted. Its only free name is `st`. EMPTY when
                 `branch` is set: a gate's verdict is not a function of any node's status, so
                 there is no predicate over `st` to write and the edge is oracle-backed instead.
        branch:  set only by `verdict()`. Marks this edge as one arm of a single decision, so the
                 translator can emit the two arms as ONE free choice rather than two.
        support: the tasks the predicate reads. graph_to_tla.py emits this as EdgeSupport, which
                 DependencyDAG.tla needs to tell a false condition that may yet become true from one
                 that cannot. Understating it lets the model cancel a live task; the differential
                 harness catches that, because evaluating the predicate outside its declared support
                 is a domain error in TLC.
        origin:  where the declaration came from, so an assumption can be found and reviewed.
        assumed: True for tier 1 (a user assertion Anchor cannot check by itself), False for the
                 combinators below.
    """

    schema: str
    tla: str
    support: tuple[str, ...]
    origin: str
    assumed: bool
    branch: "Branch | None" = None


@dataclass(frozen=True)
class Branch:
    """One gate decision, and which of its two outcomes this edge carries.

    Both arms of a `verdict()` pair share `name` and `node` and differ in `accepts`, which is how
    the translator recognises them as halves of one choice.
    """

    name: str
    node: str
    accepts: bool


def meaning(condition) -> ConditionUse | None:
    """The declared meaning of an edge condition, or None if it has none."""
    return getattr(condition, "__anchor__", None)


def graph_tla_value(v) -> str:
    """Render a Python value as TLA+. Anything not listed is refused rather than guessed at.

    NOT the same function as `translator.emit.tla_value`, which is why it does not share the name.
    That one escapes backslashes and quotes so an entity reference -- `Drupe::OAuthUser::"alice"`,
    which carries its own quotes -- does not close the TLA+ literal early. This one renders sets
    and refuses an unknown type. Each would be wrong in the other's place.
    """
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple, set, frozenset)):
        return "{" + ", ".join(graph_tla_value(x) for x in sorted(v)) + "}"
    raise TypeError(f"no TLA+ rendering for {type(v).__name__}: {v!r}")


def _names(nodes) -> tuple[str, ...]:
    """Accept all_complete("a", "b") and all_complete(["a", "b"]) alike."""
    if len(nodes) == 1 and isinstance(nodes[0], (list, tuple, set, frozenset)):
        nodes = tuple(nodes[0])
    if not nodes:
        raise ValueError("a condition over no nodes is not a condition")
    bad = [n for n in nodes if not isinstance(n, str)]
    if bad:
        raise TypeError(f"node ids must be strings; got {bad!r}")
    return tuple(sorted(set(nodes)))


def _completed(state, node_id: str) -> bool:
    """What a Strands condition can actually observe about a node.

    `state.results` gains an entry only once the node finishes, so this is False for a node that is
    pending, executing, or has not been reached.
    """
    return node_id in state.results and state.results[node_id].status == Status.COMPLETED


# ------------------------------------------------------------------------------------------------
# Tier 0: combinators whose meaning is construction rather than assertion
# ------------------------------------------------------------------------------------------------
def all_complete(*nodes):
    """AND semantics on a join: traverse only once every named node has completed.

    This is `all_dependencies_complete` from the Strands graph documentation, which every user who
    wants AND semantics is told to hand-write. Strands' default is OR — a node fires on the first
    satisfied incoming edge — so an unguarded join violates HP10.
    """
    ns = _names(nodes)

    def check(state) -> bool:
        return all(_completed(state, n) for n in ns)

    check.__anchor__ = ConditionUse(
        schema="AllComplete",
        tla=f'\\A n \\in {graph_tla_value(ns)} : st[n] = "COMPLETED"',
        support=ns,
        origin=f"{__name__}.all_complete",
        assumed=False,
    )
    return check


def any_complete(*nodes):
    """OR semantics, stated explicitly. Traverse once any named node has completed.

    Redundant against a single-parent edge, and the point on a join: it says the OR was chosen
    rather than inherited from the default.
    """
    ns = _names(nodes)

    def check(state) -> bool:
        return any(_completed(state, n) for n in ns)

    check.__anchor__ = ConditionUse(
        schema="AnyComplete",
        tla=f'\\E n \\in {graph_tla_value(ns)} : st[n] = "COMPLETED"',
        support=ns,
        origin=f"{__name__}.any_complete",
        assumed=False,
    )
    return check


def none_failed(*nodes):
    """Traverse only if no named node has failed.

    Weaker than `all_complete`: a node that has not run yet has not failed. Useful as a guard on a
    fallback edge, where waiting for completion would defeat the purpose.
    """
    ns = _names(nodes)

    def check(state) -> bool:
        return not any(
            n in state.results and state.results[n].status == Status.FAILED for n in ns
        )

    check.__anchor__ = ConditionUse(
        schema="NoneFailed",
        # CANCELED is in the spec's vocabulary but not the SDK's, and a cancelled task has no
        # result, so a condition cannot see one. Both sides therefore say "has not failed".
        tla=f'\\A n \\in {graph_tla_value(ns)} : st[n] # "FAILED"',
        support=ns,
        origin=f"{__name__}.none_failed",
        assumed=False,
    )
    return check


# The token a gate node writes into its own result to say what it decided. A gate is Anchor's own
# code, so this is a convention we SET rather than an assumption about somebody else's Python --
# which is what keeps `verdict` at tier 0 rather than tier 1.
VERDICT_PASS = "ANCHOR-VERDICT: PASS"


def _text(state, node_id: str) -> str:
    """The gate node's own account of what it decided."""
    result = state.results.get(node_id)
    return "" if result is None else str(result.result)


def verdict(node: str, *, name: str | None = None):
    """A gate's decision, as the two edges carrying its outcomes. Returns `(passed, rejected)`.

        passed, rejected = verdict("preflight")
        builder.add_edge("preflight", "score",  condition=passed)
        builder.add_edge("preflight", "report", condition=rejected)

    A GATE THAT REJECTS IS NOT A FAILED NODE. Strands' status vocabulary is PENDING / EXECUTING /
    COMPLETED / FAILED / INTERRUPTED and has no REJECTED, so a verdict has nowhere to live but the
    node's RESULT -- and `all_complete`, `any_complete` and `none_failed` all read status, so none
    of them can see it. Reaching for FAILED instead is a category error twice over: a gate that
    rejects has worked, not broken, and an AgentBase node can only reach FAILED by raising, which
    fail-fasts the entire run.

    WHY THE PAIR COMES BACK TOGETHER rather than from two calls. The arms are one decision, and
    nothing downstream could know that if they arrived separately: each opaque edge otherwise gets
    its own free oracle, so the models explore BOTH arms firing and NEITHER firing. Those are
    exactly the behaviours that break RunsAtMostOnce and NoSilentSkip, and neither is reachable in
    a workflow whose second condition is the negation of its first. Handing them over together is
    what lets the translator say so.

    `rejected` is literally `not passed`, and both require the gate to have COMPLETED -- otherwise
    the rejection arm would already be true before the gate ran, and fire immediately.
    """
    if not isinstance(node, str):
        raise TypeError(f"a gate node id must be a string; got {node!r}")
    decision = name or node

    def passed(state) -> bool:
        return _completed(state, node) and VERDICT_PASS in _text(state, node)

    def rejected(state) -> bool:
        return _completed(state, node) and VERDICT_PASS not in _text(state, node)

    for fn, accepts in ((passed, True), (rejected, False)):
        fn.__anchor__ = ConditionUse(
            schema="Verdict",
            tla="",                      # oracle-backed, not an EdgeCond arm. See ConditionUse.tla
            support=(node,),
            origin=f"{__name__}.verdict",
            assumed=False,
            branch=Branch(name=decision, node=node, accepts=accepts),
        )
    return passed, rejected


# ------------------------------------------------------------------------------------------------
# Tier 1: a user's own factory, with an asserted meaning
# ------------------------------------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def condition_schema(name: str, *, tla: str, support: tuple[str, ...] | list[str]):
    """Declare what a condition factory's closures mean, without touching what they do.

    Wraps a factory — the shape the Strands docs use, where the arguments rather than the function
    are what differ per edge — so each closure it returns carries the substituted predicate and the
    arguments it was built from.

        @condition_schema("AllComplete",
                          tla='\\A n \\in {required_nodes} : st[n] = "COMPLETED"',
                          support=("required_nodes",))
        def all_dependencies_complete(required_nodes):
            def check(state): ...
            return check

    `tla` is a template whose placeholders name the factory's parameters; `support` names the
    parameters holding the node ids the predicate reads. Both are checked against the factory's real
    signature at decoration time, so a typo fails at import rather than becoming literal text in a
    generated module.

    THE PREDICATE IS NOT VERIFIED. It is the user's assertion about their own code, and
    graph_to_tla.py reports it as an assumption. tests/strands/condition_differential.py can check
    it against the real callable, and a tier-1 condition that has not been through it is a hole.
    """

    def decorate(factory):
        params = set(inspect.signature(factory).parameters)

        unknown = {p for p in _PLACEHOLDER.findall(tla)} - params
        if unknown:
            raise ValueError(
                f"{factory.__qualname__}: tla template references {sorted(unknown)}, "
                f"which are not parameters of the factory ({sorted(params)})"
            )
        unknown = set(support) - params
        if unknown:
            raise ValueError(
                f"{factory.__qualname__}: support names {sorted(unknown)}, "
                f"which are not parameters of the factory ({sorted(params)})"
            )

        @functools.wraps(factory)
        def make(*args, **kwargs):
            bound = inspect.signature(factory).bind(*args, **kwargs)
            bound.apply_defaults()
            values = dict(bound.arguments)

            fn = factory(*args, **kwargs)  # the real condition, unmodified
            if not callable(fn):
                raise TypeError(f"{factory.__qualname__} must return a callable, got {type(fn)}")

            rendered = string.Template(
                _PLACEHOLDER.sub(r"${\1}", tla)
            ).substitute({k: graph_tla_value(v) for k, v in values.items()})

            nodes: list[str] = []
            for p in support:
                v = values[p]
                nodes.extend(_names(v if isinstance(v, (list, tuple, set, frozenset)) else (v,)))

            fn.__anchor__ = ConditionUse(
                schema=name,
                tla=rendered,
                support=tuple(sorted(set(nodes))),
                origin=f"{factory.__module__}.{factory.__qualname__}",
                assumed=True,
            )
            return fn

        return make

    return decorate
