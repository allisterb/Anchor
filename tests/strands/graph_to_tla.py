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

WHAT THIS SCRIPT NOW REPORTS. Strands decides readiness per EDGE, with OR semantics: a node fires on
the first incoming edge whose source completed and whose condition passed. An unguarded join
therefore starts before all of its parents are done, and HP10 is violated. Both graphs below are
straight out of the SDK documentation and neither carries a condition, so both go red — and the
second one is checked against the real SDK as well, so the TLA+ counterexample and the observed
execution order can be compared side by side.

The remedy is a condition on the join, which is what `specs/DependencyDAG/Workflow.tla` shows
hand-written and what tier-0 combinators will attach automatically.

    python tests/strands/graph_to_tla.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_budget import ScriptedModel  # noqa: E402

from strands import Agent  # noqa: E402
from strands.multiagent import GraphBuilder  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "DependencyDAG"
JAR = REPO / "lib" / "tla2tools-1.7.4.jar"


def agent(name: str) -> Agent:
    return Agent(model=ScriptedModel(cost=1), system_prompt=name, callback_handler=None)


def build_docs_graph():
    """The four-node workflow from the Strands graph documentation.

    research ──┬──> analysis ───┐
               └──> factcheck ──┴──> report
    """
    builder = GraphBuilder()
    for name in ("research", "analysis", "factcheck", "report"):
        builder.add_node(agent(name), name)

    builder.add_edge("research", "analysis")
    builder.add_edge("research", "factcheck")
    builder.add_edge("analysis", "report")
    builder.add_edge("factcheck", "report")
    builder.set_entry_point("research")

    return builder.build()


def build_skew_graph():
    """A join whose two parents cannot land in the same batch.

        A ──> B ──> C
        └───────────^

    The diamond above hides the OR rule, because `analysis` and `factcheck` run in one batch and
    `report` sees both complete. Here C's parents are a batch apart, so C fires off the A edge
    while B is still running — and again when B completes.
    """
    builder = GraphBuilder()
    for name in ("A", "B", "C"):
        builder.add_node(agent(name), name)

    builder.add_edge("A", "B")
    builder.add_edge("B", "C")
    builder.add_edge("A", "C")
    builder.set_entry_point("A")

    return builder.build()


class UntranslatableCondition(Exception):
    """An edge carries a condition with no declared TLA+ meaning.

    Refusing is the only sound option available today. Emitting TRUE would model an edge that always
    fires, which hides a condition that never fires and so strands its target; emitting FALSE would
    model a workflow that cannot run. The honest translation is nondeterminism, which needs the
    condition vocabulary that does not exist yet.
    """


def to_tla(graph) -> str:
    """Emit the four definitions DependencyDAG.tla expects.

    Readiness in Strands is decided per edge, not per node, so the emitted graph is `Edges` rather
    than a `Deps` AND-set — DependencyDAG.tla derives the parent set HP10 quantifies over from
    `Edges` itself, which is one fewer place for the two to disagree.

    `EdgeCond` and `EdgeSupport` are the hooks conditions will land in. Every edge here is
    unconditional, so they are constants.
    """
    nodes = sorted(graph.nodes)
    edges = sorted((e.from_node.node_id, e.to_node.node_id) for e in graph.edges)

    conditioned = [(f, t) for (f, t), e in zip(edges, sorted(
        graph.edges, key=lambda e: (e.from_node.node_id, e.to_node.node_id))) if e.condition]
    if conditioned:
        raise UntranslatableCondition(
            "no declared TLA+ meaning for the condition on: "
            + ", ".join(f"{f} -> {t}" for f, t in conditioned)
        )

    tasks = ", ".join(f'"{n}"' for n in nodes)
    edge_set = ", ".join(f'<<"{f}", "{t}">>' for f, t in edges)

    return "\n".join([
        r"\* GENERATED by tests/strands/graph_to_tla.py from a live Strands Graph.",
        r"\* Do not edit. Regenerate instead.",
        "------------------------------- MODULE Workflow -------------------------------",
        "",
        f"Tasks == {{{tasks}}}",
        "",
        f"Edges == {{{edge_set}}}",
        "",
        r"\* No edge in this graph carries a condition, so every edge is unconditional and",
        r"\* readiness is Strands' OR default: one completed parent is enough.",
        "EdgeCond(from, to, st) == TRUE",
        "",
        "EdgeSupport(from, to) == {}",
        "",
        "=============================================================================",
        "",
    ])


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
    blocks: list[list[str]] = []
    depth = 0
    collecting = False
    for line in output.splitlines():
        if re.match(r"^State \d+:", line):
            blocks.append([])
            collecting, depth = True, 0
        elif collecting and line.strip():
            blocks[-1].append(line.strip())
            depth += line.count("[") - line.count("]")
            if depth <= 0:  # the record closed; TLC's run summary follows
                collecting = False
    return [" ".join(b) for b in blocks[-last:] if b]


def describe(graph) -> None:
    print(f"    {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    for name in sorted(graph.nodes):
        parents = sorted(e.from_node.node_id for e in graph.edges if e.to_node.node_id == name)
        print(f"      {name:10} <- {parents or '(entry point)'}")


def main() -> int:
    failures = 0

    print("=" * 78)
    print("The four-node example from the Strands graph documentation")
    print("=" * 78)
    docs = build_docs_graph()
    describe(docs)

    workflow = to_tla(docs)
    print("\n  generated Workflow.tla:\n")
    print("\n".join("      " + line for line in workflow.strip().splitlines()[2:-1]))

    ok, output = check(workflow, "DependencyDAG")
    print(f"\n  HP10 + termination: {'HOLD' if ok else 'VIOLATED'}")
    if ok:
        print("  ! expected a violation: an unguarded join must break HP10 under the OR rule")
        failures += 1
    else:
        for line in counterexample(output, last=1):
            print(f"      {line}")
        print("\n  `report` starts with only one of `analysis`/`factcheck` complete. Both are")
        print("  parents, and HP10 requires both. Nothing in the SDK enforces that -- the docs")
        print("  say so: the Python default is OR semantics, and a condition is how you opt out.")

    print()
    print("=" * 78)
    print("A join whose parents are a batch apart -- checked against the real SDK too")
    print("=" * 78)
    skew = build_skew_graph()
    describe(skew)

    order = [n.node_id for n in skew("go").execution_order]
    print(f"\n  real SDK execution_order: {order}")

    # Keyed on C appearing twice, not on the order. The batch is executed concurrently, so where
    # B and the first C land relative to each other varies between runs; what does not vary is
    # that C is admitted twice. Under AND semantics C runs exactly once, after both parents.
    if order.count("C") > 1:
        print(f"  C ran {order.count('C')} times -- admitted once per satisfied incoming edge.")
        print("  Under AND semantics it would run exactly once, after both A and B.")
    else:
        print("  ! the SDK admitted C once; the OR finding would be wrong")
        failures += 1

    workflow = to_tla(skew)
    ok, output = check(workflow, "DependencyDAG")
    print(f"\n  HP10 + termination: {'HOLD' if ok else 'VIOLATED'}")
    if ok:
        print("  ! expected a violation; the model disagrees with the observed execution order")
        failures += 1
    else:
        for line in counterexample(output, last=1):
            print(f"      {line}")
        print("\n  The model and the SDK agree: C is admitted on the A edge alone, while B is")
        print("  still BLOCKED. The model stops there -- COMPLETED is terminal in it, so the")
        print("  second C the SDK runs is a gap in the model rather than a second finding.")

    print()
    print("=" * 78)
    print("The remedy, for comparison")
    print("=" * 78)
    print("  specs/DependencyDAG/Workflow.tla is the same shape with the join guarded, and it")
    print("  verifies. The guard is what `all_dependencies_complete([...])` means. Emitting it")
    print("  from the graph -- rather than writing it by hand -- is the tier-0 combinator work.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
