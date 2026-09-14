"""Anchor's OWN property-authoring pipeline, as a Strands `Graph` — checked by Anchor.

Every other graph in this directory is a shape chosen to isolate a failure class. This one is not
chosen: it is the pipeline `src/agent/author.py` and `src/agent/audit.py` already run, wired as the
`Graph` that would run it multi-agent, and put through the same two models.

    describe ──> draft ──> preflight ──> score ──> check ──> answer ──> report
                           \\_______ gate ______/

    describe    the policy's generated vocabulary            author.describe
    draft       a model proposes a module and a .cfg         author.model_author
    preflight   STATIC GATE -- undefined invariant, or a claim nothing can break
                                                             author.preflight
    score       MUTATION GATE -- holds of the policy and of every broken version of it
                                                             author.score / author.assess
    check       the checks actually run                      auto.check_all
    answer      questions.md answered, BY A DIFFERENT AGENT  auto.ask_model
    report      findings.md                                  auto.report

WHY THIS IS THE RIGHT THING TO DOGFOOD. The separation this graph exists to express -- the agent
that DRAFTS the property is not the agent that ANSWERS with it -- is the one the literature says
matters most: asked to produce both an artifact and its specification, a model finds a trivial
specification is the cheapest way to pass. Expressing that separation as a graph makes it a
structural fact instead of a convention, and puts it in front of a checker.

WHAT CAME OUT OF DOING IT, and none of it was predicted from reading the SDK:

  1. A GATE CANNOT BE A FAILING NODE. `Graph._execute_node` hardcodes an AgentBase node's status
     to COMPLETED (graph.py:1074); the only route to FAILED is raising, and that re-raises to
     fail-fast the whole run (graph.py:1147). Only a nested MultiAgentBase node can return FAILED
     and let the run continue. So `none_failed` -- our one combinator that speaks about failure --
     cannot express "the gate rejected this draft" for an agent node. The gate has to be an edge
     condition on the gate node's OUTPUT.
  2. Our tier-0 combinators read `state.results[n].status` and nothing else, so a content-reading
     gate is tier 2: opaque, and nothing about what it decides is claimed.
  3. Which means the obvious ways to wire this pipeline are all unsatisfactory, in different
     ways -- until the two arms of a gate are declared to be ONE decision (`annotations.verdict`),
     which is what the `gated` variant does and what the rest of them cannot say.
  4. And that the generic properties are the wrong question for a workflow that BRANCHES. What
     holds of `gated` and fails on everything else is the author's own claim, `AlwaysReports`,
     which no property derivable from the graph can state.

The nodes are ScriptedModel stand-ins, as everywhere else here: only the SHAPE is translated, and
the shape is the real one. Nothing in this file calls a model or spends anything.

    python tests/strands/anchor_workflow.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_to_tla import SPECS, agent, check, counterexample  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from translator import run_tlc  # noqa: E402
from translator.strands_graph_to_tla import to_tla  # noqa: E402

from annotations import verdict  # noqa: E402

from strands.multiagent import GraphBuilder  # noqa: E402

STAGES = ("describe", "draft", "preflight", "score", "check", "answer", "report")

# The four properties, each checked on its own -- TLC stops at the first violation, so a config
# listing several cannot say which shape breaks which.
PROPERTIES = ("NoSilentSkip", "HP10", "RunsAtMostOnce", "Terminates")


# ------------------------------------------------------------------------------------------------
# The gates, as they would really be written.
#
# Both read the gate node's OUTPUT, which is the only place the verdict can be -- see finding 1 in
# the module docstring. That makes them tier 2: `meaning()` returns None, the translator emits them
# in NondetEdges, and the models explore every combination of what they might decide.
# ------------------------------------------------------------------------------------------------
def _verdict(state, node: str) -> str:
    result = state.results.get(node)
    return "" if result is None else str(result.result).upper()


def preflight_passed(state) -> bool:
    return "REJECT" not in _verdict(state, "preflight")


def preflight_rejected(state) -> bool:
    return "REJECT" in _verdict(state, "preflight")


def score_discriminates(state) -> bool:
    return "WEAK" not in _verdict(state, "score")


def score_is_weak(state) -> bool:
    return "WEAK" in _verdict(state, "score")


# ------------------------------------------------------------------------------------------------
# Three ways to wire it. Every one of them is a thing somebody would actually write.
# ------------------------------------------------------------------------------------------------
def build(nodes=STAGES) -> GraphBuilder:
    builder = GraphBuilder()
    for name in nodes:
        # A DIFFERENT Agent INSTANCE PER STAGE, and the SDK requires it: `_validate_node_executor`
        # refuses a duplicate node instance (graph.py:300). So "the drafter is not the answerer"
        # is enforced at build(), by Strands, without Anchor asking for anything.
        builder.add_node(agent(name), name)
    builder.set_entry_point("describe")
    return builder


def build_pipeline():
    """The obvious wiring: a gate blocks the edge out of the gate node.

        describe -> draft -> preflight -[passed]-> score -[discriminates]-> check -> answer -> report

    Nothing downstream of a blocked gate runs, which is what a gate is FOR. The question this model
    answers is what the run then reports, and the answer is: success.
    """
    b = build()
    b.add_edge("describe", "draft")
    b.add_edge("draft", "preflight")
    b.add_edge("preflight", "score", condition=preflight_passed)
    b.add_edge("score", "check", condition=score_discriminates)
    b.add_edge("check", "answer")
    b.add_edge("answer", "report")
    return b.build()


def build_always_report():
    """The obvious FIX: route a rejection to the report so a blocked gate still says something.

        preflight -[rejected]-+
        score     -[weak]-----+--> report
        answer ---------------+

    Three parents, none of them guarded against the others, and two of them complete in earlier
    batches than the third.
    """
    b = build()
    b.add_edge("describe", "draft")
    b.add_edge("draft", "preflight")
    b.add_edge("preflight", "score", condition=preflight_passed)
    b.add_edge("preflight", "report", condition=preflight_rejected)
    b.add_edge("score", "check", condition=score_discriminates)
    b.add_edge("score", "report", condition=score_is_weak)
    b.add_edge("check", "answer")
    b.add_edge("answer", "report")
    return b.build()


def build_sequential():
    """The wiring that passes everything: no conditions at all.

    The gates still exist -- they are inside `preflight` and `score`, which short-circuit their own
    work and pass a rejection along as data. That is roughly what `author.py` does today as one
    process, and it is why this variant is not a straw man.

    Read the clean result carefully. Nothing is verified about the gates here; they have left the
    graph, so there is nothing for a graph checker to check. A property that holds because the
    thing it is about is no longer expressed is the same defect as a vacuous claim, one level up.
    """
    b = build()
    for a, z in zip(STAGES, STAGES[1:]):
        b.add_edge(a, z)
    return b.build()


def build_gated():
    """`always_report`, with each gate's two arms declared as ONE decision.

    Identical shape. The only change is that the conditions come from `verdict()` in pairs, so the
    translator can emit an ExclusivePairs entry and the models stop exploring the two behaviours a
    real gate cannot produce: both arms firing, and neither firing.
    """
    preflight_ok, preflight_no = verdict("preflight")
    score_ok, score_no = verdict("score")

    b = build()
    b.add_edge("describe", "draft")
    b.add_edge("draft", "preflight")
    b.add_edge("preflight", "score", condition=preflight_ok)
    b.add_edge("preflight", "report", condition=preflight_no)
    b.add_edge("score", "check", condition=score_ok)
    b.add_edge("score", "report", condition=score_no)
    b.add_edge("check", "answer")
    b.add_edge("answer", "report")
    return b.build()


VARIANTS = (
    ("pipeline", build_pipeline),
    ("always_report", build_always_report),
    ("gated", build_gated),
    ("sequential", build_sequential),
)

# The claim the workflow AUTHOR makes, which no generic property states: however the gates decide,
# the run reports. The graph analogue of a policy property module -- HP10 and the rest are
# DERIVABLE from any graph, this one only its author can state.
INTENT_TLA = """---------------------------- MODULE Intent ----------------------------
EXTENDS StrandsGraph

AlwaysReports == phase = "DONE" => status["report"] # "UNRUN"
=============================================================================
"""

INTENT_CFG = """SPECIFICATION Spec
CHECK_DEADLOCK FALSE
CONSTANTS
    MaxRuns = 3
INVARIANT AlwaysReports
"""


# ------------------------------------------------------------------------------------------------
class _Result:
    def __init__(self, status, result=""):
        self.status, self.result = status, result


class _State:
    def __init__(self, results):
        self.results = results


def combinator() -> int:
    """`verdict()` in Python, and what the translator makes of it.

    The declaration this combinator carries is EXCLUSIVITY, not a predicate over statuses -- so
    this is where it gets checked, rather than in condition_differential.py, whose whole subject is
    a `tla` string that a branch condition deliberately does not have.
    """
    from strands.multiagent.base import Status                    # noqa: PLC0415

    from annotations import VERDICT_PASS                          # noqa: PLC0415

    print()
    print("=" * 78)
    print("verdict(): exactly one arm, and only once the gate has spoken")
    print("=" * 78)

    passed, rejected = verdict("preflight")
    cases = [
        ("not reached yet", _State({}), False, False),
        ("completed, passed", _State({"preflight": _Result(Status.COMPLETED,
                                                           f"ok. {VERDICT_PASS}")}), True, False),
        ("completed, rejected", _State({"preflight": _Result(Status.COMPLETED,
                                                             "claim ranges over nothing")}),
         False, True),
        # A gate that crashed did not reject -- it said nothing, and the rejection arm must not
        # fire on its behalf. Both arms false leaves `report` unreached, which NoSilentSkip finds.
        ("failed", _State({"preflight": _Result(Status.FAILED, "boom")}), False, False),
    ]

    failures = 0
    print()
    for label, state, want_pass, want_reject in cases:
        got = (passed(state), rejected(state))
        ok = got == (want_pass, want_reject)
        failures += not ok
        print(f"  {label:<22} passed={got[0]!s:<6} rejected={got[1]!s:<6}"
              + ("" if ok else f"   ! expected {(want_pass, want_reject)}"))

    # And what the translator does with the pair.
    both = to_tla(build_gated())
    one_arm = to_tla(build_pipeline())
    checks = [
        ("both arms wired -> two exclusive pairs", len(both.exclusive) == 2, both.exclusive),
        ("...and no half-decisions left over", both.unpaired == [], both.unpaired),
        ("plain opaque conditions declare nothing", one_arm.exclusive == [], one_arm.exclusive),
    ]
    print()
    for label, ok, detail in checks:
        failures += not ok
        print(f"  {label:<42} {'ok' if ok else f'! {detail}'}")

    return failures


def separation() -> int:
    """The one architectural guarantee we get from `Graph` for free."""
    print()
    print("=" * 78)
    print("The separation, enforced by the SDK rather than by convention")
    print("=" * 78)

    graph = build_pipeline()
    drafter = graph.nodes["draft"].executor
    answerer = graph.nodes["answer"].executor
    distinct = drafter is not answerer
    print(f"\n  draft.executor is answer.executor: {drafter is answerer}")

    # And it cannot be otherwise: build() refuses the graph where they are the same object.
    shared = agent("both")
    b = GraphBuilder()
    b.add_node(shared, "draft")
    try:
        b.add_node(shared, "answer")
        refused = "NOT REFUSED"
        ok = False
    except ValueError as e:
        refused, ok = str(e), True

    print(f"  adding one Agent instance as two nodes: {refused}")
    print("\n  So an agent cannot draft the property it is later asked to answer with -- not")
    print("  because Anchor checks for it, but because GraphBuilder will not build that graph.")
    print("  The weaker thing it does NOT stop is two DISTINCT agents sharing a model or a")
    print("  conversation; nothing here claims otherwise.")
    return 0 if (distinct and ok) else 1


def translate(label: str, graph, show: bool = False):
    translated = to_tla(graph)
    holes, opaque = len(translated.assumptions), len(translated.nondet)
    print(f"\n  {label}")
    print(f"    assumed predicates: {holes}    not modelled: {opaque}"
          + ("" if opaque else "   (every condition came from a reviewed combinator)"))
    for f, t in translated.nondet:
        print(f"      opaque: {f} -> {t}")
    if show:
        print()
        print("\n".join("    " + line for line in translated.tla.strip().splitlines()[2:-1]))
    return translated


def check_intent(workflow_tla: str) -> tuple[bool, str]:
    """Check the AUTHOR'S claim, in a module that EXTENDS the executor model.

    Exactly the shape a policy property module has: the generic questions are derivable from the
    artifact, and this one is not derivable from anything -- only the person who wired the workflow
    knows that reporting is the point of it.
    """
    with tempfile.TemporaryDirectory(prefix="anchor-intent-") as tmp:
        work = Path(tmp)
        shutil.copy(SPECS / "strands/StrandsGraph" / "StrandsGraph.tla", work / "StrandsGraph.tla")
        (work / "Workflow.tla").write_text(workflow_tla, encoding="utf-8")
        (work / "Intent.tla").write_text(INTENT_TLA, encoding="utf-8")
        (work / "Intent.cfg").write_text(INTENT_CFG, encoding="utf-8")
        return run_tlc("Intent", work, work)


def intent(tlas: dict[str, str]) -> int:
    """`AlwaysReports`, on the two wirings that differ only in whether the arms were declared."""
    print()
    print("=" * 78)
    print("The author's own claim: however the gates decide, the run reports")
    print("=" * 78)
    print("\n  AlwaysReports == phase = \"DONE\" => status[\"report\"] # \"UNRUN\"")
    print()

    expected = {"always_report": False, "gated": True}
    failures = 0
    for label, want in expected.items():
        holds, output = check_intent(tlas[label])
        failures += holds != want
        mark = "" if holds == want else f"   ! expected {'HOLD' if want else 'VIOLATED'}"
        print(f"  {label:<16} {'HOLD' if holds else 'VIOLATED'}{mark}")
        if not holds:
            for line in counterexample(output, last=1):
                print(f"      {line}")

    print("\n  Same graph, same gates, same opacity about what either gate will decide. The only")
    print("  difference is that `gated` declared the two arms to be one decision -- and that is")
    print("  the whole distance between a claim we cannot make and one that is proved.")
    return failures


def matrix() -> tuple[int, dict[str, str]]:
    """Every property against every wiring, one invariant at a time."""
    print()
    print("=" * 78)
    print("Anchor's own pipeline, against the executor Strands actually runs")
    print("=" * 78)

    tlas = {label: translate(label, make()).tla for label, make in VARIANTS}

    # What we expect, so a change in either model or translator shows up as a mismatch rather than
    # as a differently-shaped table nobody reads.
    expected = {
        "NoSilentSkip":   {"pipeline": False, "always_report": False,
                           "gated": False, "sequential": True},
        "HP10":           {"pipeline": True,  "always_report": False,
                           "gated": False, "sequential": True},
        "RunsAtMostOnce": {"pipeline": True,  "always_report": False,
                           "gated": True,  "sequential": True},
        "Terminates":     {"pipeline": True,  "always_report": True,
                           "gated": True,  "sequential": True},
    }

    print()
    print(f"  {'':<16} " + "".join(f"{label:<18}" for label, _ in VARIANTS))

    failures = 0
    traces: dict[tuple[str, str], str] = {}
    for prop in PROPERTIES:
        cells = []
        for label, _ in VARIANTS:
            holds, output = check(tlas[label], "strands/StrandsGraph/StrandsGraph", invariant=prop)
            ok = holds == expected[prop][label]
            failures += not ok
            if not holds:
                traces[(prop, label)] = "; ".join(counterexample(output, last=1)) or "(no state)"
            cells.append(("ok" if holds else "VIOLATED") + ("" if ok else " !"))
        print(f"  {prop:<16} " + "".join(f"{c:<18}" for c in cells))

    for (prop, label), state in traces.items():
        print(f"\n  {prop} / {label}")
        print(f"      {state}")

    return failures, tlas


def main() -> int:
    failures = combinator()
    failures += separation()

    print()
    print("=" * 78)
    print("The generated workflow, for the wiring anyone would write first")
    print("=" * 78)
    translate("pipeline", build_pipeline(), show=True)

    grid, tlas = matrix()
    failures += grid
    failures += intent(tlas)

    print()
    print("=" * 78)
    print("What this says. Read the `gated` column against `always_report`")
    print("=" * 78)
    print("""
  pipeline       The gate works and the run reports success having produced nothing. Nobody was
                 told the property was rejected, because `report` is downstream of the gate that
                 rejected it -- the exact failure mode of a gated multi-agent workflow, where the
                 gate holds and its silence is indistinguishable from a pass.

  always_report  Routing the rejection to `report` breaks two more things. `report` is admitted
                 off the rejection edge while `answer` is still unrun, and admitted AGAIN when
                 `answer` completes: charged twice, second findings.md over the first.

  gated          The SAME graph, with each gate's two arms declared as one decision. The models
                 stop exploring the two behaviours a real gate cannot produce -- both arms firing,
                 and neither -- and RunsAtMostOnce goes green. Nothing else changed: not the
                 shape, not the Python, not what either gate is known to decide.

  sequential     Everything holds, and nothing was checked. The gates moved inside the nodes, so
                 they are no longer in the graph, and a graph checker has nothing to say about a
                 gate it cannot see.

  WHAT EXCLUSIVITY BOUGHT, EXACTLY ONE THING, and it is worth being precise about which.
  RunsAtMostOnce needed both arms TRUE and is now unreachable. NoSilentSkip needed both FALSE --
  also now unreachable -- but it STILL fails, and for a different reason: on the rejection branch
  `score`, `check` and `answer` are legitimately never run. Its counterexample changed rather than
  disappearing, and reads honestly now: report COMPLETED, the rest UNRUN.

  WHICH IS THE REAL FINDING. NoSilentSkip and HP10 are both universally quantified over tasks --
  every node must run, every parent must have completed -- and a BRANCH violates both by design.
  They were written for a graph in which every node is meant to run. Neither is wrong; both are
  the wrong question for a workflow that chooses.

  The right question is the author's, and no generic property can state it: *however the gates
  decide, the run reports*. That is `AlwaysReports` above -- VIOLATED on `always_report`, HOLDS on
  `gated`. It is the graph analogue of a policy property module, and the same division holds:
  HP10, NoSilentSkip, RunsAtMostOnce and Terminates are DERIVABLE from any graph, and this one
  only the person who wired the workflow can state.

  So the shape to ship is `gated` plus a stated intent -- not a green matrix, which only
  `sequential` achieves and only by removing what was being checked.
""")

    print("=" * 78)
    print("all expectations matched" if not failures else f"{failures} MISMATCHED")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
