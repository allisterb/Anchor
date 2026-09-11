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
first incoming edge whose source completed and whose condition passed. An unguarded join can
therefore start before all of its parents are done — but only when those parents cannot share a
batch, which is why the shape matters as much as the graph.

The scenarios run each graph unguarded and guarded, and the last section runs every graph against
BOTH models with the SDK's own behaviour beside them:

    DependencyDAG   the Host Agent of arXiv:2510.14133. Cancels an orphaned subgraph; requires
                    every task to terminate. No notion of a batch, so it over-approximates.
    StrandsGraph    the executor Strands actually runs. Batch, await, recompute, fail fast, stop.

They disagree in both directions, and neither is simply wrong — see cross_model() below. Read a
DependencyDAG violation as "worth checking", not as "your workflow is broken".

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
SPECS = REPO / "specs"

from _toolchain import find_jar  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SPECS / "strands" / "DependencyDAG"))

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


def one_invariant(cfg: str, invariant: str) -> str:
    """The same config, checking exactly one invariant.

    TLC stops at the first violation it finds, so a config listing several cannot say which shape
    breaks which property — on the skew graph both HP10 and RunsAtMostOnce fire, and only the first
    is reported. Constants and CHECK_DEADLOCK are kept; every INVARIANT and PROPERTY line is
    dropped and the one under test appended.
    """
    kept = [ln for ln in cfg.splitlines()
            if not ln.strip().startswith(("INVARIANT", "PROPERTY"))]
    return "\n".join(kept + [f"INVARIANT {invariant}", ""])


def check(workflow_tla: str, spec: str, invariant: str | None = None) -> tuple[bool, str]:
    """Run one spec against the generated workflow, in a scratch directory.

    `spec` is a path under specs/ ending in the module name -- "strands/DependencyDAG/DependencyDAG"
    -- so the same generated graph can be checked against both DependencyDAG (the paper's
    orchestrator) and StrandsGraph (the executor Strands runs). Split from the RIGHT, so regrouping
    specs/ into subdirectories does not need this line changed again.

    Copied out rather than run in place so a generated Workflow.tla never overwrites the
    hand-written one the checked-in specs are verified against.
    """
    folder, spec = spec.rsplit("/", 1)
    with tempfile.TemporaryDirectory(prefix="anchor-graph-") as tmp:
        work = Path(tmp)
        for name in (f"{spec}.tla", f"{spec}.cfg"):
            shutil.copy(SPECS / folder / name, work / name)
        (work / "Workflow.tla").write_text(workflow_tla, encoding="utf-8")

        if invariant is not None:
            cfg = work / f"{spec}.cfg"
            cfg.write_text(one_invariant(cfg.read_text(encoding="utf-8"), invariant),
                           encoding="utf-8")

        proc = subprocess.run(
            ["java", "-cp", str(find_jar()), "tlc2.TLC", "-cleanup",
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

    ok, output = check(translated.tla, "strands/DependencyDAG/DependencyDAG")
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
    print("\n  DependencyDAG admits `report` with only one of `analysis`/`factcheck` complete, and")
    print("  HP10 requires both. But READ THIS ONE CAREFULLY: the real executor cannot do that on")
    print("  THIS shape. Both parents are seeded into one batch, _execute_nodes_parallel awaits")
    print("  all of it, and readiness is recomputed only afterwards -- so `report` always sees")
    print("  both. Probed 3/3: execution_order is research, analysis, factcheck, report.")
    print("\n  DependencyDAG.tla does not model batches, so it interleaves tasks individually and")
    print("  over-approximates. Holds there still means holds in reality; VIOLATED there may be")
    print("  spurious, as it is here. specs/strands/StrandsGraph models the batch loop and clears this")
    print("  graph. The violation below, on a shape whose parents cannot share a batch, is real")
    print("  in both models and in the SDK.")

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

    failures += cross_model()
    failures += invariant_matrix()

    print()
    print("=" * 78)
    print(f"{'all scenarios matched expectation' if not failures else f'{failures} MISMATCHED'}")
    print("=" * 78)

    return 1 if failures else 0


def invariant_matrix() -> int:
    """Which StrandsGraph property each shape breaks, one invariant at a time.

    TLC stops at the first violation, so the combined config cannot attribute a failure: on the
    skew graph both HP10 and RunsAtMostOnce fire and only HP10 is reported. Checking them
    separately is what makes each finding attributable to the shape that causes it -- and pins the
    table in specs/strands/StrandsGraph/README.md, which was otherwise a claim nothing re-checked.
    """
    print()
    print("=" * 78)
    print("Which StrandsGraph property each shape breaks")
    print("=" * 78)

    shapes = [
        ("unguarded diamond", build_docs_graph(False)),
        ("skew", build_skew_graph(False)),
        ("router", build_router_graph()),
    ]
    # Each finding belongs to exactly one shape. A row that goes all-ok means the property stopped
    # biting; a row that lights up everywhere means it stopped being specific.
    expected = {
        "NoSilentSkip":   {"unguarded diamond": True, "skew": True,  "router": False},
        "HP10":           {"unguarded diamond": True, "skew": False, "router": True},
        "RunsAtMostOnce": {"unguarded diamond": True, "skew": False, "router": True},
    }

    tlas = {label: to_tla(graph).tla for label, graph in shapes}
    print(f"\n  {'':<16} " + "".join(f"{label:<20}" for label, _ in shapes))

    failures = 0
    for invariant, per_shape in expected.items():
        cells = []
        for label, _ in shapes:
            holds, _ = check(tlas[label], "strands/StrandsGraph/StrandsGraph", invariant=invariant)
            ok = holds == per_shape[label]
            failures += not ok
            cells.append(("ok" if holds else "VIOLATED") + ("" if ok else " !"))
        print(f"  {invariant:<16} " + "".join(f"{c:<20}" for c in cells))

    print("\n  NoSilentSkip is the router's: the run reports success with `approve` never executed.")
    print("  HP10 and RunsAtMostOnce are both the skew's, and both are real -- C is admitted while")
    print("  B is still running, and then admitted a second time when B completes. The diamond")
    print("  breaks none of them, because its parents share a batch.")

    return failures


def cross_model() -> int:
    """The same graph against both models, with the SDK's own behaviour beside them.

    They model different orchestrators, and neither is a refinement of the other:

      DependencyDAG   the Host Agent of arXiv:2510.14133. Cancels an orphaned subgraph; requires
                      every task to terminate. Interleaves tasks individually, with no notion of a
                      batch -- so it ADMITS BEHAVIOURS STRANDS CANNOT PRODUCE.
      StrandsGraph    the executor Strands actually runs. Batch, await the whole batch, recompute
                      readiness, fail fast, stop when nothing is ready.

    The two disagreements below go in opposite directions, which is the point of running both.
    """
    print()
    print("=" * 78)
    print("The same graph against both models, and against the SDK")
    print("=" * 78)

    cases = [
        ("docs diamond, unguarded", build_docs_graph(False), False, True,
         "report ran 1x, after both parents (3/3 runs)"),
        ("docs diamond, guarded", build_docs_graph(True), True, True,
         "report ran 1x"),
        ("skew, unguarded", build_skew_graph(False), False, False,
         "C ran 2x -- admitted while B was still running"),
        ("skew, guarded", build_skew_graph(True), True, True,
         "C ran 1x"),
        ("router, opaque conditions", build_router_graph(), True, False,
         "COMPLETED having run 2/3 nodes; `approve` skipped"),
    ]

    print(f"\n  {'graph':<26} {'DependencyDAG':<15} {'StrandsGraph':<14} the SDK")
    print(f"  {'-' * 26} {'-' * 15} {'-' * 14} {'-' * 44}")

    failures = 0
    for label, graph, dag_holds, sg_holds, observed in cases:
        tla = to_tla(graph).tla
        dag, _ = check(tla, "strands/DependencyDAG/DependencyDAG")
        sg, _ = check(tla, "strands/StrandsGraph/StrandsGraph")

        mark = ""
        if (dag, sg) != (dag_holds, sg_holds):
            mark, failures = "   ! unexpected", failures + 1
        print(f"  {label:<26} {'HOLD' if dag else 'VIOLATED':<15} "
              f"{'HOLD' if sg else 'VIOLATED':<14} {observed}{mark}")

    print("""
  Two disagreements, in opposite directions, and neither model is simply wrong.

  The DIAMOND. DependencyDAG says VIOLATED; the executor cannot do it. Both parents are seeded
  into one batch and awaited together, so `report` always sees both. DependencyDAG has no batches
  and interleaves tasks individually, so it over-approximates: HOLD there means holds in reality,
  but VIOLATED may be spurious -- as it is here.

  The ROUTER. DependencyDAG says HOLD; the executor drops a node. That is not imprecision, it is
  a different machine: DependencyDAG's orchestrator CANCELS what it cannot admit, so every task
  reaches a terminal state and the property is satisfied honestly. Strands has no cancellation and
  no CANCELED status -- it stops and reports success. A whole failure class that the paper's model
  cannot express, because its orchestrator does not have the behaviour.

  Which is the argument for keeping both. Check the paper's properties against DependencyDAG; ask
  what your workflow will actually do against StrandsGraph.""")

    return failures


if __name__ == "__main__":
    sys.exit(main())
