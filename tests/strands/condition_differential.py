"""Differential test: does an edge condition's TLA+ predicate agree with the Python it annotates?

The problem this addresses. `specs/strands/DependencyDAG/anchor_conditions.py` attaches a TLA+ predicate to
a Strands edge condition, and `graph_to_tla.py` emits that predicate into the generated workflow. If
the predicate and the callable disagree, nothing fails — the model verifies, and it verifies a
workflow nobody is running. That is the same trap as a hand-written condition-language translator,
which is the thing annotations were chosen over; annotations are only better if the claim they make
is actually checked.

So: don't trust the annotation, test it. Enumerate every assignment of task states over the
condition's declared support, ask the real callable for a verdict on each, and let TLC compare that
table against the predicate. A disagreement comes back as a counterexample naming the exact state.

    anchor_conditions ──┬── predicate ────────────────────┐
                        │                                  ├──> TLC checks Agree
                        └── the callable, on real ─────────┘
                            GraphState objects (oracle)

What is trusted by reading, and what is not:

  - DependencyDAG.tla    hand-written, reviewed once.
  - the predicate        under test. It is the thing that could be wrong.
  - the callable         not trusted, measured. It is what Strands will actually run.

THE STATE VOCABULARIES DIFFER, AND THAT MAPPING IS UNDER TEST TOO. The spec has six states; the SDK
has five, sharing only COMPLETED and FAILED, and a condition sees neither directly — it reads
`state.results`, which gains an entry only once a node finishes. So the oracle builds a GraphState
in which BLOCKED, READY, IN_PROGRESS and CANCELED all appear as an absent result, and the predicate
has to agree with that or fail here.

SCOPE. The oracle populates `NodeResult.status` and nothing else, so a condition that reads result
*content* — the agent's text, or the `invocation_state` dict — is out of scope by construction.
Those are exactly the conditions that cannot be given a predicate over the spec's vocabulary
either, and they belong in tier 2 as nondeterministic edges.

    python tests/strands/condition_differential.py
"""

from __future__ import annotations

import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "strands" / "DependencyDAG"

from _toolchain import find_jar  # noqa: E402

sys.path.insert(0, str(SPECS))

from anchor_conditions import (  # noqa: E402
    STATES, all_complete, any_complete, condition_schema, meaning, none_failed,
)

from strands.multiagent.base import NodeResult, Status  # noqa: E402
from strands.multiagent.graph import GraphState  # noqa: E402


# ------------------------------------------------------------------------------------------------
# The oracle: what the real callable says, on real GraphState objects
# ------------------------------------------------------------------------------------------------
def graph_state(assignment: dict[str, str]) -> GraphState:
    """A GraphState in which each node carries the spec state named by `assignment`.

    `results` is what an edge condition can see, and Strands writes an entry only when a node
    finishes. COMPLETED and FAILED therefore map to a NodeResult; BLOCKED, READY, IN_PROGRESS and
    CANCELED all map to no entry at all — the SDK has no status for any of them that a condition
    could observe, and no CANCELED status at all.
    """
    sdk = {"COMPLETED": Status.COMPLETED, "FAILED": Status.FAILED}
    results = {
        node: NodeResult(result=Exception("scripted"), status=sdk[spec_state])
        for node, spec_state in assignment.items()
        if spec_state in sdk
    }
    return GraphState(results=results)


def build_oracle(condition, support: tuple[str, ...]) -> dict[tuple[str, ...], bool]:
    """Ask the callable for a verdict on every assignment of states over its declared support."""
    return {
        combo: bool(condition(graph_state(dict(zip(support, combo)))))
        for combo in itertools.product(STATES, repeat=len(support))
    }


# ------------------------------------------------------------------------------------------------
# Emit the generated TLA+ module and check it
# ------------------------------------------------------------------------------------------------
def _fn(support: tuple[str, ...], combo: tuple[str, ...]) -> str:
    """One assignment as a TLA+ function, via TLC's :> and @@.

    Written as a function rather than a record because a node id need not be a legal TLA+ record
    field name, and the ids come from a user's graph.
    """
    return " @@ ".join(f'("{n}" :> "{s}")' for n, s in zip(support, combo))


def generate_module(tla: str, support: tuple[str, ...], oracle: dict) -> str:
    entries = " @@\n".join(
        f"    ({_fn(support, combo)}) :> {'TRUE' if verdict else 'FALSE'}"
        for combo, verdict in sorted(oracle.items())
    )
    supp = ", ".join(f'"{n}"' for n in support)
    states = ", ".join(f'"{s}"' for s in sorted(STATES))

    return f"""\\* GENERATED by tests/strands/condition_differential.py -- do not edit.
\\* Predicate from anchor_conditions; Oracle measured from the real Python callable.
------------------------- MODULE ConditionDifferential -------------------------
EXTENDS TLC

Support == {{{supp}}}
States == {{{states}}}

\\* The predicate under test, exactly as graph_to_tla.py would emit it into Workflow.tla.
Cond(st) == {tla}

\\* What the callable said, keyed by the assignment it was asked about.
Oracle ==
  (
{entries}
  )

\\* Every assignment over the declared support. If the predicate reads a task outside Support it
\\* indexes st outside its domain, and TLC reports that here -- which is how an understated
\\* EdgeSupport gets caught rather than silently letting the model cancel a live task.
Agree == \\A f \\in [Support -> States] : Cond(f) = Oracle[f]

VARIABLE done
Init == done = FALSE
Next == UNCHANGED done
Spec == Init /\\ [][Next]_done

=============================================================================
"""


CONFIG = """\
SPECIFICATION Spec
CHECK_DEADLOCK FALSE
INVARIANT Agree
"""


def check(module_text: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="anchor-cond-") as tmp:
        work = Path(tmp)
        (work / "ConditionDifferential.tla").write_text(module_text, encoding="utf-8")
        (work / "ConditionDifferential.cfg").write_text(CONFIG, encoding="utf-8")

        proc = subprocess.run(
            ["java", "-cp", str(find_jar()), "tlc2.TLC", "-cleanup",
             "-metadir", str(work / "states"),
             "-config", "ConditionDifferential.cfg", "ConditionDifferential.tla"],
            cwd=work, capture_output=True, text=True,
        )
        return proc.returncode == 0, proc.stdout + proc.stderr


def compare(label: str, condition, expect_agree: bool = True) -> bool:
    """Check one annotated condition. Returns True if the outcome matched expectation."""
    use = meaning(condition)
    if use is None:
        print(f"  {label:<42} NO DECLARATION")
        return False

    oracle = build_oracle(condition, use.support)
    agreed, output = check(generate_module(use.tla, use.support, oracle))

    tier = "assumed" if use.assumed else "combinator"
    verdict = "AGREE" if agreed else "DISAGREE"
    matched = agreed == expect_agree
    print(f"  {label:<42} {len(oracle):>4} states  {tier:<10} {verdict}"
          + ("" if matched else f"   ! expected {'AGREE' if expect_agree else 'DISAGREE'}"))
    if not agreed and expect_agree:
        for line in output.splitlines():
            if "Error:" in line:
                print(f"      {line.strip()}")
    return matched


# ------------------------------------------------------------------------------------------------
# Tier 1, as a user would write it: the factory straight out of the Strands docs, annotated
# ------------------------------------------------------------------------------------------------
@condition_schema(
    "AllComplete",
    tla='\\A n \\in {required_nodes} : st[n] = "COMPLETED"',
    support=("required_nodes",),
)
def all_dependencies_complete(required_nodes: list[str]):
    """Verbatim from the Strands graph documentation, with the declaration added."""

    def check_all_complete(state) -> bool:
        return all(
            node_id in state.results and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


@condition_schema(
    "AllComplete",
    # WRONG ON PURPOSE: \E where the callable means \A. If the harness cannot catch a mistranslation
    # this blatant it is checking nothing, and every AGREE above is worthless.
    tla='\\E n \\in {required_nodes} : st[n] = "COMPLETED"',
    support=("required_nodes",),
)
def mistranslated(required_nodes: list[str]):
    def check_all_complete(state) -> bool:
        return all(
            node_id in state.results and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


def main() -> int:
    print("Tier 0 -- combinators, whose meaning is construction rather than assertion")
    results = [
        compare('all_complete("a", "b")', all_complete("a", "b")),
        compare('any_complete("a", "b")', any_complete("a", "b")),
        compare('none_failed("a", "b")', none_failed("a", "b")),
        compare('all_complete("a", "b", "c")', all_complete("a", "b", "c")),
    ]

    print("\nTier 1 -- a user's own factory, with an asserted meaning")
    results.append(
        compare('all_dependencies_complete(["a", "b"])', all_dependencies_complete(["a", "b"]))
    )

    print("\nMutation -- the same callable with a deliberately wrong predicate")
    results.append(
        compare('mistranslated(["a", "b"])', mistranslated(["a", "b"]), expect_agree=False)
    )

    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} of {len(results)} did not match expectation")
        return 1
    print(f"all {len(results)} matched expectation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
