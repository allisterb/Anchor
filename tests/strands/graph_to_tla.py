"""Translate a Strands agent graph into the TLA+ the DependencyDAG properties are stated over.

The point. Verifying a workflow means having a model of it, and a model written by reading code is a
paraphrase that nothing checks. But a Strands `Graph` is not a description of a workflow — it *is*
the workflow, built with `GraphBuilder` and executed as-is. Walking that object is therefore
translation, not inference: the thing we model and the thing that runs cannot drift apart, because
they are the same object.

    GraphBuilder ──> Graph ──> Workflow.tla ──┐
                                              ├──> TLC checks HP10 + termination
                       DependencyDAG.tla ─────┘

Only the graph is generated. The properties and the transition logic live once in DependencyDAG.tla,
which EXTENDS the generated module — so a new workflow is checked against the same reviewed
properties without anyone rewriting them.

There is no DOT or mermaid export in the SDK to translate instead; the mermaid blocks in the Strands
docs are hand-drawn illustrations. The object graph is the artifact, and it is the better one — no
format, no parser, nothing to fall out of step.

WHAT THIS SCRIPT SHOWS. Strands decides readiness per EDGE, with OR semantics: a node fires on the
first incoming edge whose source completed and whose condition passed. Four runs below, two graphs
each unguarded and guarded:

  - unguarded, the shape as the Strands docs write it -> HP10 VIOLATED. The join starts before all
    of its parents are done, and nothing in the runtime prevents it.
  - guarded with `all_complete(...)` from specs/DependencyDAG/anchor_conditions.py -> HP10 holds.

The second graph is checked against the real SDK as well, so the TLA+ result and the observed
execution order can be compared directly: unguarded, the join runs twice; guarded, once.

    python tests/strands/graph_to_tla.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "DependencyDAG"
JAR = REPO / "lib" / "tla2tools-1.7.4.jar"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SPECS))

from anchor_conditions import ConditionUse, all_complete, meaning  # noqa: E402
from shared_budget import ScriptedModel  # noqa: E402

from strands import Agent  # noqa: E402
from strands.multiagent import GraphBuilder  # noqa: E402


def agent(name: str) -> Agent:
    return Agent(model=ScriptedModel(cost=1), system_prompt=name, callback_handler=None)


def build_docs_graph(guarded: bool):
    """The four-node workflow from the Strands graph documentation.

    research ──┬──> analysis ───┐
               └──> factcheck ──┴──> report
    """
    join = all_complete("analysis", "factcheck") if guarded else None

    builder = GraphBuilder()
    for name in ("research", "analysis", "factcheck", "report"):
        builder.add_node(agent(name), name)

    builder.add_edge("research", "analysis")
    builder.add_edge("research", "factcheck")
    builder.add_edge("analysis", "report", condition=join)
    builder.add_edge("factcheck", "report", condition=join)
    builder.set_entry_point("research")

    return builder.build()


def build_skew_graph(guarded: bool):
    """A join whose two parents cannot land in the same batch.

        A ──> B ──> C
        └───────────^

    The diamond above hides the OR rule, because `analysis` and `factcheck` run in one batch and
    `report` sees both complete. Here C's parents are a batch apart, so unguarded C fires off the
    A edge while B is still running — and again when B completes.
    """
    join = all_complete("A", "B") if guarded else None

    builder = GraphBuilder()
    for name in ("A", "B", "C"):
        builder.add_node(agent(name), name)

    builder.add_edge("A", "B")
    builder.add_edge("B", "C", condition=join)
    builder.add_edge("A", "C", condition=join)
    builder.set_entry_point("A")

    return builder.build()


def approved(state) -> bool:
    """An opaque condition — tier 2, and genuinely untranslatable.

    It reads the agent's output text, which is not in the spec's vocabulary and could not be given a
    predicate over it. This is the category `nondet` exists for, not a gap someone forgot to fill.
    """
    result = state.results.get("plan")
    return result is not None and "approve" in str(result.result).lower()


def rejected(state) -> bool:
    result = state.results.get("plan")
    return result is not None and "approve" not in str(result.result).lower()


def build_router_graph():
    """Conditional routing on what an agent said.

               ┌──> approve
        plan ──┤
               └──> reject

    Both edges are opaque. Every target has one parent, so an edge can only fire once that parent
    has completed — which is HP10, whatever the conditions decide.
    """
    builder = GraphBuilder()
    for name in ("plan", "approve", "reject"):
        builder.add_node(agent(name), name)

    builder.add_edge("plan", "approve", condition=approved)
    builder.add_edge("plan", "reject", condition=rejected)
    builder.set_entry_point("plan")

    return builder.build()


def build_opaque_join_graph():
    """The same opacity on a join, where it costs something.

        a ──┐
            ├──> z
        b ──┘

    Nothing says the conditions wait for both parents, so the combination where one fires alone is
    a behaviour of this workflow — and it violates HP10.
    """
    builder = GraphBuilder()
    for name in ("a", "b", "z"):
        builder.add_node(agent(name), name)

    builder.add_edge("a", "z", condition=approved)
    builder.add_edge("b", "z", condition=rejected)
    builder.set_entry_point("a")
    builder.set_entry_point("b")

    return builder.build()


class UntranslatableCondition(Exception):
    """A declaration that cannot be emitted — a support set naming a task outside the graph."""


@dataclass
class Translation:
    tla: str
    assumptions: list[tuple[tuple[str, str], ConditionUse]]  # tier-1 holes, edge -> declaration
    nondet: list[tuple[str, str]]                            # tier-2 edges, condition not modelled


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
    for e in edges:
        pair = (e.from_node.node_id, e.to_node.node_id)
        if e.condition is None:
            continue
        use = meaning(e.condition)
        if use is None:
            nondet.append(pair)   # tier 2: modelled as an unknown-but-fixed choice
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
        r"\* GENERATED by tests/strands/graph_to_tla.py from a live Strands Graph.",
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
    if nondet:
        header += [
            r"\*",
            r"\* NOT MODELLED. These conditions have no declared meaning, so nothing about what",
            r"\* they decide is claimed. Anything proved below holds for every combination of",
            r"\* their outcomes -- and a property that depends on one of them will not prove.",
        ] + [
            rf"\*   <<{f!r}, {t!r}>>".replace("'", '"') for f, t in nondet
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
    body += [
        "",
        f"NondetEdges == {{{nondet_set}}}",
        "",
        "=============================================================================",
        "",
    ]

    return Translation(tla="\n".join(header + body), assumptions=assumed, nondet=nondet)


def check(workflow_tla: str, spec: str) -> tuple[bool, str]:
    """Run one DependencyDAG spec against the generated workflow, in a scratch directory.

    Copied out rather than run in place so a generated Workflow.tla never overwrites the
    hand-written one the checked-in specs are verified against.
    """
    with tempfile.TemporaryDirectory(prefix="anchor-graph-") as tmp:
        work = Path(tmp)
        for name in (f"{spec}.tla", f"{spec}.cfg"):
            shutil.copy(SPECS / name, work / name)
        (work / "Workflow.tla").write_text(workflow_tla, encoding="utf-8")

        proc = subprocess.run(
            ["java", "-cp", str(JAR), "tlc2.TLC", "-cleanup",
             "-metadir", str(work / "states"), "-config", f"{spec}.cfg", f"{spec}.tla"],
            cwd=work, capture_output=True, text=True,
        )
        return proc.returncode == 0, proc.stdout + proc.stderr


def counterexample(output: str, last: int = 1) -> list[str]:
    """The final states of TLC's counterexample, each flattened onto one line.

    TLC wraps a wide state record over several lines, so this collects each `State n:` block rather
    than matching single lines.
    """
    # TLC ends a state block with a blank line, except for the last one in a run, which runs
    # straight into the progress summary. Both endings are matched rather than guessed at by
    # bracket depth -- a two-variable state is a conjunction, so the first conjunct balances its
    # own brackets while the block continues.
    summary = re.compile(r"^(\d+ states generated|The depth |Progress\(|Finished |Model checking|"
                         r"Error|\s*Estimates|\s*calculated)")
    blocks: list[list[str]] = []
    collecting = False
    for line in output.splitlines():
        if re.match(r"^State \d+:", line):
            blocks.append([])
            collecting = True
        elif collecting and (not line.strip() or summary.match(line)):
            collecting = False
        elif collecting:
            blocks[-1].append(line.strip())
    return [" ".join(b) for b in blocks[-last:] if b]


def run_scenario(title: str, graph, expect_hold: bool, show_tla: bool = False) -> bool:
    """Generate, check, and report one graph. Returns True if TLC agreed with the expectation."""
    print(f"\n{title}")
    print("-" * len(title))

    translated = to_tla(graph)
    if show_tla:
        print()
        print("\n".join("    " + line for line in translated.tla.strip().splitlines()[2:-1]))

    holes, opaque = len(translated.assumptions), len(translated.nondet)
    if holes or opaque:
        print(f"\n  assumed predicates: {holes}    not modelled: {opaque}")
    else:
        print("\n  assumed predicates: 0    not modelled: 0"
              "  (every condition came from a reviewed combinator)")

    ok, output = check(translated.tla, "DependencyDAG")
    verdict = "HOLD" if ok else "VIOLATED"
    agreed = ok == expect_hold
    print(f"  HP10 + termination: {verdict}"
          + ("" if agreed else f"   ! expected {'HOLD' if expect_hold else 'VIOLATED'}"))
    if not ok:
        for line in counterexample(output, last=1):
            print(f"      {line}")
    return agreed


def main() -> int:
    failures = 0

    print("=" * 78)
    print("The four-node example from the Strands graph documentation")
    print("=" * 78)
    failures += not run_scenario(
        "unguarded, as the docs write it", build_docs_graph(guarded=False),
        expect_hold=False, show_tla=True)
    print("\n  `report` starts with only one of `analysis`/`factcheck` complete. Both are parents,")
    print("  and HP10 requires both. Nothing in the runtime prevents it -- the docs say so: the")
    print("  Python default is OR semantics, and a condition is how you opt out.")

    failures += not run_scenario(
        "guarded with all_complete(\"analysis\", \"factcheck\")", build_docs_graph(guarded=True),
        expect_hold=True, show_tla=True)

    print()
    print("=" * 78)
    print("A join whose parents are a batch apart -- checked against the real SDK too")
    print("=" * 78)

    for guarded, expect_runs in ((False, 2), (True, 1)):
        label = "guarded" if guarded else "unguarded"
        order = [n.node_id for n in build_skew_graph(guarded)("go").execution_order]
        runs = order.count("C")
        # Keyed on how many times C is admitted, not on the order: the batch executes concurrently,
        # so where B and a first C land relative to each other varies between runs. The count does
        # not. Under AND semantics C is admitted exactly once, after both parents.
        mark = "" if runs == expect_runs else f"   ! expected C {expect_runs}x"
        failures += runs != expect_runs
        print(f"\n  real SDK, {label:<9} execution_order: {str(order):<32} C ran {runs}x{mark}")

    failures += not run_scenario("unguarded", build_skew_graph(False), expect_hold=False)
    print("\n  The model and the SDK agree: C is admitted on the A edge alone, while B is still")
    print("  BLOCKED. The model stops there -- COMPLETED is terminal in it, so the second C the")
    print("  SDK runs is a gap in the model rather than a second finding.")

    failures += not run_scenario("guarded with all_complete(\"A\", \"B\")", build_skew_graph(True),
                                 expect_hold=True)

    print()
    print("=" * 78)
    print("Tier 2 -- conditions with no declared meaning, modelled as an unknown choice")
    print("=" * 78)
    print("  `approved(state)` reads the agent's output text. That is not in the spec's")
    print("  vocabulary and no predicate over it exists, so nothing is claimed about what it")
    print("  decides: TLC runs the workflow once per combination of outcomes.")

    failures += not run_scenario(
        "routing on an opaque condition -- one parent per target", build_router_graph(),
        expect_hold=True, show_tla=True)
    print("\n  HP10 holds for every combination. Each target has a single parent, so an edge can")
    print("  only fire once that parent completed -- true whatever the condition says. A real")
    print("  result about a workflow whose conditions were never translated.")

    failures += not run_scenario(
        "the same opacity on a join", build_opaque_join_graph(), expect_hold=False)
    print("\n  And the honest limit. Nothing says these conditions wait for both parents, so the")
    print("  combination where one fires alone is a behaviour of this workflow. Tier 2 cannot")
    print("  clear it; declaring the condition -- tier 0 or 1 -- is the only way through.")

    print()
    print("=" * 78)
    print("Why an edge that never fires does not hang the graph")
    print("=" * 78)
    graph = build_router_graph()
    result = graph("go")
    ran = [n.node_id for n in result.execution_order]
    skipped = sorted(set(graph.nodes) - set(ran))
    print(f"  real SDK: status={result.status}, ran {ran}, "
          f"{result.completed_nodes}/{result.total_nodes} nodes, skipped {skipped}")
    print("\n  The scripted model never says \"approve\", so that branch's condition never passes")
    print("  and the node never runs. Strands does not wait for it: when nothing is ready the run")
    print("  ENDS, and it ends reporting COMPLETED. A node can be silently dropped from a")
    print("  workflow that reports success -- which is why AllTerminate is a property of the")
    print("  MODEL here, not a claim about the runtime.")

    print()
    print("=" * 78)
    print(f"{'all scenarios matched expectation' if not failures else f'{failures} MISMATCHED'}")
    print("=" * 78)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
