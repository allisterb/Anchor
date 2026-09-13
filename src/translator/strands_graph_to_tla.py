"""Translate a live Strands `Graph` into the TLA+ that `DependencyDAG.tla` checks.

A model written by reading code is a paraphrase, and nothing checks a paraphrase. A Strands `Graph`
is not a *description* of a workflow: `GraphBuilder` is the construction API, so the graph IS the
workflow and the runtime executes that same object. Walking it is translation, not inference.

    GraphBuilder ──> Graph ──> Workflow.tla ──┐
                                              ├──> TLC checks HP10 + termination
                       DependencyDAG.tla ─────┘

WHAT AN EDGE CONDITION MEANS is the whole difficulty, and it is not decided here -- `meaning()` in
`anchor_conditions` decides it, and this module reports what it was told:

    tier 0  a combinator carrying its own TLA+ predicate; meaning by construction
    tier 1  a user's `@condition_schema` assertion, which is a HOLE in every proof and is listed
            as one rather than absorbed
    tier 2  no declaration, so the edge is emitted as nondeterministic and nothing is claimed

The split is the point: a meaning is declared where the WORKFLOW is written, by the person who
wrote the condition, and this module only reports what it was told. It never decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from annotations import ConditionUse, meaning

class UntranslatableCondition(Exception):
    """A declaration that cannot be emitted — a support set naming a task outside the graph."""


@dataclass
class Translation:
    tla: str
    assumptions: list[tuple[tuple[str, str], ConditionUse]]  # tier-1 holes, edge -> declaration
    nondet: list[tuple[str, str]]                            # tier-2 edges, condition not modelled
    exclusive: list[tuple[str, tuple[str, str], tuple[str, str]]] = field(default_factory=list)
    unpaired: list[tuple[str, tuple[str, str]]] = field(default_factory=list)


def to_tla(graph) -> Translation:
    """Emit the four definitions DependencyDAG.tla expects.

    Readiness in Strands is decided per edge, not per node, so the emitted graph is `Edges` rather
    than a `Deps` AND-set — DependencyDAG.tla derives the parent set HP10 quantifies over from
    `Edges` itself, which is one fewer place for the two to disagree.
    """
    nodes = sorted(graph.nodes)
    edges = sorted(graph.edges, key=lambda e: (e.from_node.node_id, e.to_node.node_id))

    declared: list[tuple[tuple[str, str], ConditionUse]] = []
    nondet: list[tuple[str, str]] = []
    branches: dict[str, dict[bool, tuple[str, str]]] = {}
    for e in edges:
        pair = (e.from_node.node_id, e.to_node.node_id)
        if e.condition is None:
            continue
        use = meaning(e.condition)
        if use is None:
            nondet.append(pair)   # tier 2: modelled as an unknown-but-fixed choice
        elif use.branch is not None:
            # A GATE'S VERDICT. Still a free choice -- nothing here knows what the gate will
            # decide -- but the two arms of one decision are not free of EACH OTHER, and that is
            # the whole content of the declaration. Recorded now, emitted as ExclusivePairs below.
            arms = branches.setdefault(use.branch.name, {})
            if use.branch.accepts in arms:
                raise UntranslatableCondition(
                    f"decision {use.branch.name!r} has two edges carrying its "
                    f"{'accepting' if use.branch.accepts else 'rejecting'} arm: "
                    f"{arms[use.branch.accepts]} and {pair}. Pass `name=` to verdict() to "
                    f"separate two decisions on one gate node")
            arms[use.branch.accepts] = pair
            nondet.append(pair)
        else:
            declared.append((pair, use))

    # A support set naming a node that is not in the graph would index `state` outside its domain,
    # which TLC reports as an opaque evaluation error deep in a trace. Catch it here instead.
    for (f, t), use in declared:
        stray = [n for n in use.support if n not in graph.nodes]
        if stray:
            raise UntranslatableCondition(
                f"condition on {f} -> {t} reads {stray!r}, which are not nodes in this graph"
            )
        if not use.tla:
            raise UntranslatableCondition(
                f"condition on {f} -> {t} declares no predicate and is not a branch")

    # A decision with only one arm wired is NOT an error -- it is the pipeline whose rejection goes
    # nowhere, which is a thing people write. There is simply no exclusivity to declare about a
    # single edge, so it stays an ordinary free choice, and NoSilentSkip is left free to find it.
    exclusive = [(name, arms[True], arms[False])
                 for name, arms in sorted(branches.items()) if len(arms) == 2]
    unpaired = [(name, next(iter(arms.values())))
                for name, arms in sorted(branches.items()) if len(arms) == 1]

    def case(arms: list[tuple[tuple[str, str], str]], otherwise: str, indent: str = "    ") -> str:
        if not arms:
            return otherwise
        width = max(len(f'<<from, to>> = <<"{f}", "{t}">>') for (f, t), _ in arms)
        lines = [
            f'{indent}{"CASE" if i == 0 else "  []"} '
            f'{f"<<from, to>> = <<\"{f}\", \"{t}\">>":<{width}} -> {body}'
            for i, (((f, t), body)) in enumerate(arms)
        ]
        lines.append(f'{indent}  [] {"OTHER":<{width}} -> {otherwise}')
        return "\n" + "\n".join(lines)

    tasks = ", ".join(f'"{n}"' for n in nodes)
    edge_set = ", ".join(f'<<"{e.from_node.node_id}", "{e.to_node.node_id}">>' for e in edges)

    cond_arms = [(pair, use.tla) for pair, use in declared]
    supp_arms = [(pair, "{" + ", ".join(f'"{n}"' for n in use.support) + "}") for pair, use in declared]

    header = [
        r"\* GENERATED by src/translator/strands_graph_to_tla.py from a live Strands Graph.",
        r"\* Do not edit. Regenerate instead.",
    ]
    assumed = [(pair, use) for pair, use in declared if use.assumed]
    if assumed:
        header += [
            r"\*",
            r"\* ASSUMED. These predicates are user assertions about their own Python, which",
            r"\* Anchor does not verify. Each is a hole in every proof below.",
        ] + [
            rf"\*   {use.schema:<14} <<{f!r}, {t!r}>>  from {use.origin}".replace("'", '"')
            for (f, t), use in assumed
        ]
    # Branch edges are free choices too, but something IS declared about them, so listing them
    # under "nothing is claimed" would be false.
    branch_edges = {p for _, a, b in exclusive for p in (a, b)} | {p for _, p in unpaired}
    opaque = [p for p in nondet if p not in branch_edges]

    if opaque:
        header += [
            r"\*",
            r"\* NOT MODELLED. These conditions have no declared meaning, so nothing about what",
            r"\* they decide is claimed. Anything proved below holds for every combination of",
            r"\* their outcomes -- and a property that depends on one of them will not prove.",
        ] + [
            rf"\*   <<{f!r}, {t!r}>>".replace("'", '"') for f, t in opaque
        ]
    if exclusive:
        header += [
            r"\*",
            r"\* ONE DECISION, TWO ARMS. What the gate decides is still unknown; what is declared",
            r"\* is that these two edges are the SAME decision, so exactly one of them fires.",
            r"\* Without it the models explore both firing and neither, and neither behaviour is",
            r"\* reachable in a workflow whose second condition is the negation of its first.",
        ] + [
            rf"\*   {name:<14} accept <<{a[0]!r}, {a[1]!r}>>  reject <<{b[0]!r}, {b[1]!r}>>"
            .replace("'", '"') for name, a, b in exclusive
        ]
    if unpaired:
        header += [
            r"\*",
            r"\* HALF A DECISION. Only one arm of each of these is wired into the graph, so the",
            r"\* other outcome leads nowhere and there is no exclusivity to declare. Left as an",
            r"\* ordinary free choice.",
        ] + [
            rf"\*   {name:<14} <<{p[0]!r}, {p[1]!r}>>".replace("'", '"') for name, p in unpaired
        ]

    body = [
        "------------------------------- MODULE Workflow -------------------------------",
        "",
        f"Tasks == {{{tasks}}}",
        "",
        f"Edges == {{{edge_set}}}",
        "",
    ]
    if not declared:
        body += [
            r"\* No edge in this graph carries a condition with a declared meaning, so EdgeCond is",
            r"\* vacuous. An edge with no condition at all is Strands' OR default: one completed",
            r"\* parent is enough.",
            "EdgeCond(from, to, st) == TRUE",
            "",
            "EdgeSupport(from, to) == {}",
        ]
    else:
        body += [
            f"EdgeCond(from, to, st) =={case(cond_arms, 'TRUE')}",
            "",
            f"EdgeSupport(from, to) =={case(supp_arms, '{}')}",
        ]

    nondet_set = ", ".join(f'<<"{f}", "{t}">>' for f, t in nondet)
    # << accepting edge, rejecting edge >>, so the model can constrain one oracle to be the
    # negation of the other. Empty for every graph without a gate, where the conjunct that reads
    # it is vacuous and nothing about those checks changes.
    pairs = ", ".join(f'<< <<"{a[0]}", "{a[1]}">>, <<"{b[0]}", "{b[1]}">> >>'
                      for _, a, b in exclusive)
    body += [
        "",
        f"NondetEdges == {{{nondet_set}}}",
        "",
        f"ExclusivePairs == {{{pairs}}}",
        "",
        "=============================================================================",
        "",
    ]

    return Translation(tla="\n".join(header + body), assumptions=assumed, nondet=nondet,
                       exclusive=exclusive, unpaired=unpaired)
