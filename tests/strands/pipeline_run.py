"""`src/agent/pipeline.py` end to end, and the claim that makes it worth having.

Three things are checked here, and the third is the one the whole graph exercise was for:

  1. A REJECTED DRAFT still reports. The static gate turns the draft away, `score`, `check` and
     `answer` never run -- no TLC, no second model call -- and findings.md says what was rejected
     and that nothing was verified.
  2. AN ACCEPTED DRAFT goes the whole way, and the answerer sees the verdicts rather than the
     drafter's reasoning.
  3. THE SHAPE THAT RUNS IS THE SHAPE THAT WAS CHECKED. `to_tla` over the graph `pipeline.build`
     actually returns must carry both gate decisions as ExclusivePairs, and must satisfy
     `AlwaysReports` -- the same claim, over the same module, that tests/strands/anchor_workflow.py
     proves about the `gated` variant. Without this the design work checked a drawing.

No provider and no credentials: both agents are scripted, so the only cost is the TLC runs behind
the `score` gate in scenario 2.

    python tests/strands/pipeline_run.py
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchor_workflow import check_intent                               # noqa: E402
from translator.strands_graph_to_tla import to_tla                     # noqa: E402

from strands import Agent                                              # noqa: E402
from strands.models import Model                                       # noqa: E402
from strands.types.content import Messages                             # noqa: E402
from strands.types.event_loop import Usage                             # noqa: E402
from strands.types.tools import ToolSpec                               # noqa: E402

from agent import pipeline                                             # noqa: E402

POLICIES = REPO / "tests" / "policies"


class Fixed(Model):
    """A model that says one thing. Stands in for the drafter and the answerer."""

    def __init__(self, text: str) -> None:
        self.text, self.calls = text, 0

    def get_config(self) -> Any:
        return {}

    def update_config(self, **model_config: Any) -> None:
        pass

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError

    async def stream(self, messages: Messages, tool_specs: list[ToolSpec] | None = None,
                     system_prompt: str | None = None, tool_choice: Any | None = None, *,
                     system_prompt_content=None, **kwargs: Any) -> AsyncGenerator[Any, None]:
        self.calls += 1
        self.seen = pipeline.incoming(messages)
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": self.text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": Usage(inputTokens=0, outputTokens=0, totalTokens=0),
                            "metrics": {"latencyMs": 0}}}


def agent(text: str, name: str) -> Agent:
    return Agent(model=Fixed(text), callback_handler=None, name=name)


# A draft that holds and discriminates: tests/policies/firewall.tla, renamed to the module name the
# loop chose. Real, and checked in -- inventing one here would be checking the harness.
GOOD = "===MODULE===\n" + (POLICIES / "firewall.tla").read_text(encoding="utf-8").replace(
    "MODULE firewall", "MODULE Intent", 1) + "\n===CONFIG===\n" + (
    POLICIES / "firewall.cfg").read_text(encoding="utf-8")

# A draft whose .cfg names an invariant the module never defines. TLC would stop with an error
# rather than check anything, which is why this is a hard rejection and not a warning.
BAD = """===MODULE===
---------------------------- MODULE Intent ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest
VARIABLE req
Init == req = 1
Next == UNCHANGED req
Spec == Init /\\ [][Next]_req
=============================================================================
===CONFIG===
SPECIFICATION Spec
INVARIANT OutsideIsRefused
"""

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        failures.append(label)
        if detail:
            print(f"          {detail[:400]}")


def run_pipeline(draft: str, out: Path, mutants: int = 2):
    run = pipeline.Run(policy=POLICIES / "firewall.dw",
                       intent="SSH from the local range is permitted, and every external source "
                              "is denied.",
                       out=out, mutants=mutants)
    drafter, answerer = agent(draft, "draft"), agent("The property held.", "answer")
    graph = pipeline.build(run, drafter=drafter, answerer=answerer)
    result = graph("State and check the intention for firewall.dw.")
    return run, result, [n.node_id for n in result.execution_order], answerer


def rejected_path() -> None:
    print("\nA draft the static gate turns away")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        run, result, ran, answerer = run_pipeline(BAD, Path(tmp))

        print(f"  ran {len(ran)}/{result.total_nodes}: {', '.join(ran)}")
        check("rejected at preflight", run.rejected_at == "preflight", str(run.complaints))
        check("the complaint names the undefined invariant",
              any("OutsideIsRefused" in c for c in run.complaints), str(run.complaints))

        # THE POINT OF GATING BEFORE THE EXPENSIVE STEP. Nothing downstream ran: no TLC, and the
        # second model was never called.
        check("score, check and answer never ran",
              not ({"score", "check", "answer"} & set(ran)), str(ran))
        check("the answerer was not invoked", answerer.model.calls == 0)

        # ...and it still reported, which is the property `AlwaysReports` states.
        check("report ran anyway", "report" in ran, str(ran))
        check("findings.md exists", run.findings is not None and run.findings.exists())
        text = run.findings.read_text(encoding="utf-8") if run.findings else ""
        check("findings.md says nothing was verified", "nothing here was verified" in text)
        check("...and names the gate", "`preflight`" in text, text[:200])


def accepted_path() -> None:
    print("\nA draft that holds and discriminates")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        run, result, ran, answerer = run_pipeline(GOOD, Path(tmp))

        print(f"  ran {len(ran)}/{result.total_nodes}: {', '.join(ran)}")
        check("not rejected", run.rejected_at == "", run.rejected_at or "")
        check("every stage ran", set(ran) == set(pipeline.STAGES), str(sorted(set(ran))))
        check("the property was scored against mutants", run.score.get("caught") is not None,
              str(run.score.get("exitCode")))
        check("the checks ran", bool(run.checked), run.checked[:200])

        # THE SEPARATION, as it actually lands: the answerer's input contains the verdicts and not
        # the drafter's module text. Nothing enforces this but the wiring, so it is checked.
        seen = getattr(answerer.model, "seen", "")
        check("the answerer saw the verdicts", "The stated property" in seen, seen[:200])
        check("the answerer did NOT see the draft", "===MODULE===" not in seen, seen[:200])

        # THE BOUND REACHES THE REPORTER. "Holds" on its own is the most overclaimable sentence
        # this pipeline emits, and a live run produced exactly the overclaim -- "for all possible
        # requests and scenarios", "guaranteed" -- because nothing it was given said otherwise.
        check("the answerer was told what the property RANGES OVER",
              "WHAT WAS ACTUALLY CHECKED" in seen and "claim" in seen, seen[-300:])
        check("...including the states each claim applies to",
              "applies" in seen, seen[-300:])

        text = run.findings.read_text(encoding="utf-8") if run.findings else ""
        check("findings.md carries the verdicts", "## Verdicts" in text)
        check("...and says the property was agent-authored", "weaker evidence" in text)

        # Strands frames a node's input; that framing was landing in findings.md under a heading
        # promising the reporter's own words.
        check("the report does not carry Strands' input scaffolding",
              "Inputs from previous nodes" not in text and "Original Task:" not in text,
              text[-400:])


def same_object() -> None:
    """The claim the graph work exists to support."""
    print("\nThe shape that runs is the shape that was checked")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        run = pipeline.Run(policy=POLICIES / "firewall.dw", intent="x", out=Path(tmp))
        graph = pipeline.build(run, drafter=agent(GOOD, "draft"), answerer=agent("ok", "answer"))

        t = to_tla(graph)
        check("both gates declared as exclusive decisions", len(t.exclusive) == 2, str(t.exclusive))
        check("no half-decisions", t.unpaired == [], str(t.unpaired))
        check("no undeclared assumptions", t.assumptions == [], str(t.assumptions))

        for name, a, b in t.exclusive:
            print(f"    {name:<10} accept {a}   reject {b}")

        holds, output = check_intent(t.tla)
        check("AlwaysReports HOLDS on the graph that actually runs", holds,
              "\n".join(output.splitlines()[-8:]))

        # The separation, enforced by the SDK rather than by this file.
        check("the drafter and the answerer are different objects",
              graph.nodes["draft"].executor is not graph.nodes["answer"].executor)


def main() -> int:
    print("=" * 78)
    print("Anchor's property-authoring pipeline, as the graph that runs it")
    print("=" * 78)

    same_object()
    rejected_path()
    accepted_path()

    print()
    print("=" * 78)
    print("all checks passed" if not failures else f"{len(failures)} FAILED: {failures}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
