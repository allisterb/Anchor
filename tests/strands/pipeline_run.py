"""`src/agent/pipeline.py` end to end, and the claim that makes it worth having.

Six scenarios, and the first is the one the whole graph exercise was for:

  1. THE SHAPE THAT RUNS IS THE SHAPE THAT WAS CHECKED. `to_tla` over the graph `pipeline.build`
     actually returns must carry both gate decisions as exclusive pairs, and must satisfy
     `AlwaysReports` -- the same claim, over the same module, that tests/strands/anchor_workflow.py
     proves about the `gated` variant. Without this the design work checked a drawing.
  2. A DRAFT THAT WILL NOT COMPILE is retried, having been told the line and the token. This is
     the failure a live run hit, over one stray `*`. The retry lives inside the `draft` node, so
     the graph stays acyclic -- asserted, because a cycle would put it outside what either model
     can express.
  3. RUNNING OUT OF ROUNDS is not a crash and not a silence: the last attempt is judged by the
     same gates, and findings.md says the allowance ran out.
  4. A BUDGET CAP is neither a bad draft nor a finished report. A cut-off draft is a failed
     round; a cut-off report says so of itself, because a truncated report that does not reads
     as a complete one.
  5. A REJECTED DRAFT still reports, without a TLC run or a second model call.
  6. AN ACCEPTED DRAFT goes the whole way, and the answerer sees the verdicts and their BOUND
     rather than the drafter's module.

No provider and no credentials: every agent is scripted, so the only cost is the TLC runs behind
the `score` gate.

    python tests/strands/pipeline_run.py
"""

from __future__ import annotations

import re
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
        # A FIXED, NON-ZERO COST PER CALL. Zero would make the accounting untestable: the whole
        # question is whether a second call to the SAME agent reports its own usage or the running
        # total, and 0 + 0 looks the same either way.
        yield {"metadata": {"usage": Usage(inputTokens=10, outputTokens=5, totalTokens=15),
                            "metrics": {"latencyMs": 0}}}


class Scripted(Fixed):
    """A different reply per call, so a retry can be told apart from a repeat."""

    def __init__(self, *texts: str) -> None:
        super().__init__(texts[0])
        self.texts, self.prompts = texts, []

    async def stream(self, messages, *a, **kw):                # type: ignore[override]
        self.prompts.append(pipeline.incoming(messages))
        self.text = self.texts[min(self.calls, len(self.texts) - 1)]
        async for event in super().stream(messages, *a, **kw):
            yield event


class Capped(Fixed):
    """Stops the way a tripped budget cap stops: a stop_reason, and a truncated reply.

    Simulated rather than provoked, because a `turns` cap cannot fire on an agent with no tools --
    one turn always completes. The shape is what matters and it is the SDK's own: stop_reason
    `limit_turns` / `limit_total_tokens` / `limit_output_tokens`, returned normally.
    """

    def __init__(self, text: str, reason: str = "limit_output_tokens") -> None:
        super().__init__(text)
        self.reason = reason

    async def stream(self, messages, *a, **kw):                # type: ignore[override]
        self.calls += 1
        self.seen = pipeline.incoming(messages)
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": self.text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": self.reason}}


def agent(text: str, name: str) -> Agent:
    return Agent(model=Fixed(text), callback_handler=None, name=name)


def scripted(name: str, *texts: str) -> Agent:
    return Agent(model=Scripted(*texts), callback_handler=None, name=name)


# The draft a live run actually produced: right in every respect but one stray `*` after a comment
# terminator, which SANY rejects and no amount of re-reading catches.
WONT_COMPILE = "===MODULE===\n" + (POLICIES / "firewall_unparseable.tla").read_text(
    encoding="utf-8").replace("MODULE firewall_unparseable", "MODULE Intent", 1) + (
    "\n===CONFIG===\n" + (POLICIES / "firewall.cfg").read_text(encoding="utf-8"))


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


def run_pipeline(draft, out: Path, mutants: int = 2, rounds: int = 3):
    run = pipeline.Run(policy=POLICIES / "firewall.dw",
                       intent="SSH from the local range is permitted, and every external source "
                              "is denied.",
                       out=out, mutants=mutants, rounds=rounds)
    drafter = draft if isinstance(draft, Agent) else agent(draft, "draft")
    answerer = agent("The property held.", "answer")
    graph = pipeline.build(run, drafter=drafter, answerer=answerer)
    result = graph("State and check the intention for firewall.dw.")
    pipeline.append_usage(run, result)
    return run, result, [n.node_id for n in result.execution_order], answerer


def retries() -> None:
    """The failure a live run hit: a module that will not compile, fixed by being told where."""
    print("\nA draft that does not compile, and the round that fixes it")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        drafter = scripted("draft", WONT_COMPILE, GOOD)
        run, result, ran, _ = run_pipeline(drafter, Path(tmp))

        print(f"  ran {len(ran)}/{result.total_nodes}: {', '.join(ran)}  "
              f"({run.round} drafting round(s))")
        check("it took a second round", run.round == 2, str(run.round))
        check("and the run then completed", set(ran) == set(pipeline.STAGES), str(sorted(set(ran))))
        check("not rejected", run.rejected_at == "", run.rejected_at)

        # A complaint without a LOCATION is one no round can act on. SANY has it; nothing else in
        # the pipeline does.
        second = drafter.model.prompts[1]                      # type: ignore[attr-defined]
        check("round 2 was told the module did not compile",
              "did not compile" in second, second[:200])
        check("...and where SANY choked",
              "Parse Error" in second and re.search(r"at line \d+, column \d+", second) is not None,
              second[-400:])

        # THE RETRY IS INSIDE ONE NODE, which is why the graph is still acyclic and still the
        # shape the models checked. If `draft` ever starts appearing twice, a cycle has been
        # introduced and neither model can express it -- see stage_draft's docstring.
        check("the graph stayed acyclic: draft ran once", ran.count("draft") == 1, str(ran))

        # THE ACCOUNTING TRAP, and this is the only scenario that can catch it: the drafter is
        # called TWICE on the same Agent object. `metrics.accumulated_usage` is cumulative across
        # invocations, so reading it per call would bill round 1 again on round 2 -- 15 then 30,
        # totalling 45 for two calls that each cost 15. Silent, and it grows with the round count.
        drafts = [c for c in run.calls if c.who.startswith("draft")]
        check("two drafting rounds were billed", len(drafts) == 2, str([c.who for c in run.calls]))
        check("...each at ITS OWN cost, not the agent's running total",
              [c.total for c in drafts] == [15, 15], str([c.total for c in drafts]))


def capped() -> None:
    """A budget cap must not read as a bad draft, or as a finished report."""
    print("\nA budget cap fires")
    print("-" * 78)

    # --- the DRAFTER is cut off -------------------------------------------------------------
    # Left alone this reaches the gates as a half-written module, is rejected for not compiling,
    # and the report blames the model for a syntax error that was really a budget running out.
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        cut = Agent(model=Capped("===MODULE===\n---- MODULE Int"), callback_handler=None,
                    name="draft")
        run, result, ran, _ = run_pipeline(cut, Path(tmp), rounds=2)

        check("a cut-off draft is a failed round, not a draft",
              run.round == 2 and run.exhausted, f"round={run.round} exhausted={run.exhausted}")
        check("and the cap is recorded against the round that hit it",
              len(run.capped) == 2 and "draft round 1" in run.capped[0], str(run.capped))
        check("the run still reported", "report" in ran, str(ran))

        text = run.findings.read_text(encoding="utf-8") if run.findings else ""
        check("findings.md leads with the cap", "A budget cap fired" in text, text[:300])
        check("...and names which cap", "limit_output_tokens" in text, text[:400])

    # --- the REPORTER is cut off -------------------------------------------------------------
    # The dangerous one: a truncated report that does not say so reads as a complete one, and
    # nothing in the verdicts would tell the reader otherwise.
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        run = pipeline.Run(policy=POLICIES / "firewall.dw", intent="x", out=Path(tmp), mutants=2)
        graph = pipeline.build(run, drafter=agent(GOOD, "draft"),
                               answerer=Agent(model=Capped("The property h"),
                                              callback_handler=None, name="answer"))
        result = graph("go")
        ran = [n.node_id for n in result.execution_order]

        check("the run completed", set(ran) == set(pipeline.STAGES), str(sorted(set(ran))))
        check("the cap on the reporter was caught",
              any("the report" in c for c in run.capped), str(run.capped))
        text = run.findings.read_text(encoding="utf-8") if run.findings else ""
        check("the report says of ITSELF that it is incomplete",
              "cut off by a budget cap and is incomplete" in text, text[-400:])


def exhausted() -> None:
    """Running out of rounds is not a crash, and must not be a silent one either."""
    print("\nRounds exhausted")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-pipe-") as tmp:
        drafter = scripted("draft", WONT_COMPILE)              # never improves
        run, result, ran, answerer = run_pipeline(drafter, Path(tmp), rounds=2)

        print(f"  ran {len(ran)}/{result.total_nodes}: {', '.join(ran)}  "
              f"({run.round} round(s), exhausted={run.exhausted})")
        check("every round was used", run.round == 2, str(run.round))
        check("and the allowance is recorded as spent", run.exhausted is True)
        check("the run was NOT aborted", result.status.value != "failed", str(result.status))
        check("report still ran", "report" in ran, str(ran))
        check("the answerer was not invoked", answerer.model.calls == 0)

        text = run.findings.read_text(encoding="utf-8") if run.findings else ""
        check("findings.md says the allowance ran out", "allowance ran out" in text, text[:400])
        check("...and that nothing was verified", "nothing here was verified" in text)


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

        # --- WHAT IT COST ---------------------------------------------------------------------
        check("findings.md reports the cost", "## What this run cost" in text, text[-600:])
        check("one row per model call", len(run.calls) == 2,
              str([c.who for c in run.calls]))
        check("and a per-stage time for every stage that ran",
              all(f"  {s:<12}" in text for s in pipeline.STAGES), text[-800:])

        check("with the tokens each one cost", all(c.total == 15 for c in run.calls),
              str([(c.who, c.total) for c in run.calls]))


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
    retries()
    capped()
    exhausted()
    rejected_path()
    accepted_path()

    print()
    print("=" * 78)
    print("all checks passed" if not failures else f"{len(failures)} FAILED: {failures}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
