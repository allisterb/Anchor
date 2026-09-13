"""Anchor's property-authoring pipeline, as the Strands `Graph` that runs it.

    describe ──> draft ──> preflight ──┬──> score ──┬──> check ──> answer ──> report
                                       │            │                          ^  ^
                                       └────────────┴──────────────────────────┘  │
                                            a rejection still reports ────────────┘

THE SEPARATION IS THE POINT. The agent that DRAFTS the property is not the agent that ANSWERS with
it. Asked to produce both an artifact and its specification, a model finds that a trivial
specification is the cheapest way to pass -- the most-reported pathology in agentic verification,
and the reason this is two agents rather than one with two prompts. `GraphBuilder` enforces it:
one Agent instance cannot be two nodes, and neither sees the other's context.

WHAT IS A MODEL'S DECISION AND WHAT IS NOT. Only `draft` and `answer` are language models. The five
other nodes are `Computed`: ordinary Python behind the same interface, so the graph is uniform
while the criteria stay in code where nothing can negotiate with them.

  describe   the vocabulary, from the checker  (author.describe)
  draft      MODEL. Proposes a module and a .cfg
  preflight  GATE, static: an invariant the .cfg names but the module never defines, or a claim
             nothing it ranges over can break                            (author.preflight)
  score      GATE, adversarial: does the property hold of every BROKEN version of the policy too?
             If so it constrains nothing                          (author.score, author.assess)
  check      the checks actually run             (repair.run_checker, repair.check_property)
  answer     MODEL, a DIFFERENT one. Answers in prose from the verdicts
  report     findings.md, on every path including both rejections

A GATE THAT REJECTS IS NOT A FAILED NODE. It completes, writes its verdict into its own result, and
two `verdict()` edges route on it -- declared as one decision, so the model checker knows exactly
one arm fires. See `annotations.verdict` for why that mattered, and
`tests/strands/anchor_workflow.py` for the four properties this shape was chosen against. The graph
built here is the `gated` variant of that file, which is the point: the shape that was checked and
the object that runs are the same object.

    python src/agent/pipeline.py examples/aws1/07-trust-decay.dw \\
        --intent "After 15 minutes without advisor interaction, the agent loses write access."
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from strands import Agent                                              # noqa: E402
from strands.models import Model                                       # noqa: E402
from strands.multiagent import GraphBuilder                            # noqa: E402
from strands.types.content import Messages                             # noqa: E402
from strands.types.event_loop import Usage                             # noqa: E402
from strands.types.tools import ToolSpec                               # noqa: E402

from annotations import VERDICT_PASS, verdict                          # noqa: E402

from agent import author, repair                                       # noqa: E402

STAGES = ("describe", "draft", "preflight", "score", "check", "answer", "report")

ANSWERER_PROMPT = (
    "You report formal verification results to the person who owns the policy. You are given a "
    "property module somebody else drafted, and the verdicts a model checker returned for it.\n\n"
    "Say what was checked, what held, and what did not. Quote the counterexample in the policy "
    "author's own terms -- a request or a session they could try -- never as a TLA+ state.\n\n"
    "You did not write the property and you cannot change it. If the property does not appear to "
    "state what the stated intention meant, say so plainly: that is a finding about the property, "
    "and it is more useful than a verdict about the policy. Do not claim anything was verified "
    "that the verdicts below do not say was verified.\n\n"
    "STATE THE BOUND EVERY TIME, and state it concretely. A property ranges over exactly the "
    "values it names -- the verdicts tell you which, and how many states each claim applies to. "
    "'Holds' means it held over those. Never write 'for all possible requests', 'in every "
    "scenario', 'guaranteed', or 'no situations exist': the check did not establish any of them, "
    "and a reader who believes it will stop looking. Name the values that were checked instead, "
    "and say what was not.")


# ------------------------------------------------------------------------------------------------
# A node that is not a language model
# ------------------------------------------------------------------------------------------------
class Computed(Model):
    """Runs Python and returns its text, behind the `Model` interface a graph node needs.

    A Strands graph node is an `AgentBase` or a nested `MultiAgentBase` and nothing else
    (graph.py:1083), so a deterministic stage has to arrive as one or the other. This is the
    cheaper of the two and it keeps the graph uniform: every node is an Agent, and whether its
    answer came from a model or from a function is a property of the node rather than of the
    wiring.

    It costs nothing and reports nothing: zero tokens, no network, no credentials.
    """

    def __init__(self, run, fn) -> None:
        self.run, self.fn = run, fn

    def get_config(self) -> Any:
        return {}

    def update_config(self, **model_config: Any) -> None:
        pass

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("a computed node has no structured output")

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        tool_choice: Any | None = None,
        *,
        system_prompt_content=None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        text = self.fn(self.run, incoming(messages))

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": Usage(inputTokens=0, outputTokens=0, totalTokens=0),
                            "metrics": {"latencyMs": 0}}}


def incoming(messages: Messages) -> str:
    """Everything the parents said, as one string.

    `Graph._build_node_input` formats parent results into a text block, so a stage that wants what
    its parent produced reads it here. Most do not -- they read `Run`, because a path or a verdict
    dictionary does not survive a round trip through prose.
    """
    return "\n".join(
        block.get("text", "")
        for m in messages if m.get("role") == "user"
        for block in m.get("content", []) if isinstance(block, dict))


def unframe(text: str) -> str:
    """Just what the parent said, without `_build_node_input`'s scaffolding around it.

    Strands frames a node's input as `Original Task: ...` / `Inputs from previous nodes:` /
    `From <node>:` / `  - Agent: <text>`. Useful to a model, and it was landing verbatim in
    findings.md under a heading that promised the answerer's report.

    This parses another library's PRESENTATION format, which is the kind of thing that breaks
    quietly on an upgrade -- so it falls back to the whole string rather than to an empty one. A
    report with some scaffolding in it is a blemish; a report with nothing in it is a lie.
    """
    marker = "\n  - Agent: "
    if marker not in text:
        return text.strip()

    body = text.rsplit(marker, 1)[1]
    # Continuation lines are indented to match; the first is not, having followed the marker.
    return "\n".join(line[4:] if line.startswith("    ") else line
                     for line in body.splitlines()).strip()


# ------------------------------------------------------------------------------------------------
@dataclass
class Run:
    """What the stages share. The graph gives ordering; this carries the structure."""

    policy: Path
    intent: str
    out: Path
    event_schema: Path | None = None
    module_name: str = "Intent"
    mutants: int = 8
    rounds: int = 3

    round: int = 0
    attempts: list[str] = field(default_factory=list)
    exhausted: bool = False

    vocab: dict = field(default_factory=dict)
    module: str = ""
    config: str = ""
    module_path: Path | None = None
    complaints: list[str] = field(default_factory=list)
    score: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    prop: dict = field(default_factory=dict)
    explained: str = ""
    checked: str = ""
    answered: str = ""
    rejected_at: str = ""
    findings: Path | None = None


def gate(ok: bool, said: str) -> str:
    """A gate's own account of what it decided, in the form `verdict()` reads."""
    return f"{VERDICT_PASS}\n{said}" if ok else f"ANCHOR-VERDICT: REJECT\n{said}"


# ------------------------------------------------------------------------------------------------
# The stages
# ------------------------------------------------------------------------------------------------
def stage_describe(run: Run, _: str) -> str:
    """The vocabulary, and the request built from it. Not guessed and not asked of the model."""
    run.vocab = author.describe(run.policy, run.event_schema)
    if run.vocab.get("_failed"):
        raise RuntimeError(f"could not read {run.policy.name}: {run.vocab.get('_why')}")
    run.vocab["requiredModuleName"] = run.module_name
    return author.draft_prompt(run.vocab, run.intent)


def stage_draft(run: Run, asked: str, drafter) -> str:
    """Propose a module, and try again when it will not compile or says nothing.

    THE RETRY IS HERE AND NOT IN THE GRAPH, deliberately. A retry is a cycle, and neither model
    can express one: `oracle` is chosen in Init and never changes, so a retry edge cannot say
    "again, then stop", and StrandsGraph's StartBatch increments `runs` with no guard, so a cycle
    breaks TypeOK's `runs \\in 0..MaxRuns`. A cyclic graph here would be a graph nothing checks.
    Keeping the loop inside one node keeps the whole shape acyclic and every property we proved
    about it true -- at the price that these rounds are invisible to the model, which is a real
    limitation and is stated rather than hidden.

    ONLY THE CHEAP GATES ARE IN THE LOOP: SANY (~1s) and `preflight` (milliseconds). `score` runs
    TLC once per mutant and stays outside, one shot -- a rejection there ends the run with a
    report, which is what `AlwaysReports` guarantees.
    """
    run.out.mkdir(parents=True, exist_ok=True)
    scratch = run.out / f"{run.module_name}.tla"

    feedback = ""
    for attempt in range(1, max(1, run.rounds) + 1):
        run.round = attempt
        prompt = author.draft_prompt(run.vocab, run.intent, feedback) if feedback else asked
        text = str(drafter(prompt)).strip()
        module, config = author.parse_draft(text)
        run.attempts.append(text)

        if not module.strip() or not config.strip():
            feedback = ("Your reply did not contain both files. Return the module between "
                        "===MODULE=== and ===CONFIG===, and the .cfg after ===CONFIG===.")
            continue

        # DOES IT COMPILE? The failure a live run actually hit, and the cheapest to fix: SANY
        # names the line, the column and the token, and one more round is seconds.
        scratch.write_text(module, encoding="utf-8")
        scratch.with_suffix(".cfg").write_text(config, encoding="utf-8")
        ok, out = author.compiles(run.policy, scratch, event_schema=run.event_schema)
        if not ok:
            feedback = ("Your module did not compile. Fix exactly this and return the whole "
                        f"module again:\n\n{out[:2000]}")
            continue

        # AND DOES IT SAY ANYTHING? Free, and it is the other way a draft comes back useless.
        try:
            said = author.preflight(module, config, run.module_name)
        except Exception as e:                              # noqa: BLE001 - fed back, not raised
            feedback = f"Your module could not be read: {e}"
            continue
        if said:
            feedback = "Your draft was rejected:\n\n" + "\n".join(said) + "\n\nTry again."
            continue

        return text                                          # the gate nodes still judge it

    # Rounds exhausted. The last attempt is passed on ANYWAY rather than raising: the gates below
    # are what refuse a draft, and `report` is downstream of them. A node that raised here would
    # fail-fast the run and produce no findings.md at all -- the one outcome this shape exists to
    # prevent.
    run.exhausted = True
    return run.attempts[-1] if run.attempts else ""


def stage_preflight(run: Run, said: str) -> str:
    """The static gate. Milliseconds, against minutes for the one below it."""
    run.module, run.config = author.parse_draft(said)
    if not run.module.strip() or not run.config.strip():
        run.rejected_at = "preflight"
        run.complaints = ["the draft did not contain both a module and a .cfg between the "
                          "===MODULE=== and ===CONFIG=== markers"]
        return gate(False, run.complaints[0])

    try:
        run.complaints = author.preflight(run.module, run.config, run.module_name)
        # WHAT THE CLAIM FORBIDS, AND OVER HOW MANY STATES. Read here because the module is
        # already in hand and it costs milliseconds -- and carried all the way to `answer`,
        # because it is the only thing in the whole run that states the BOUND. Without it the
        # reporter is handed "the property HOLDS" and nothing to stop it writing "for all
        # possible requests", which is what it did.
        from checker.explain import Module, explain, render             # noqa: PLC0415
        run.explained = render(explain(Module(run.module, run.config, run.module_name)))
    except Exception as e:                                  # noqa: BLE001 - reported, not raised
        # A draft that will not even parse is a rejection, not a crash of the pipeline. The gate
        # has done its job; `report` still runs and says so.
        run.complaints = [f"the module could not be read: {e}"]

    if run.complaints:
        run.rejected_at = "preflight"
        return gate(False, "\n".join(run.complaints))
    return gate(True, "nothing statically wrong: every named invariant is defined, and each "
                      "claim ranges over states that can break it")


def stage_score(run: Run, _: str) -> str:
    """The adversarial gate: does this property notice the policy breaking?"""
    run.out.mkdir(parents=True, exist_ok=True)
    run.module_path = run.out / f"{run.module_name}.tla"
    run.module_path.write_text(run.module, encoding="utf-8")
    run.module_path.with_suffix(".cfg").write_text(run.config, encoding="utf-8")

    run.score = author.score(run.policy, run.module_path, event_schema=run.event_schema,
                             mutants=run.mutants)
    run.complaints = author.assess(run.score, run.config)
    if run.complaints:
        run.rejected_at = "score"
        return gate(False, "\n".join(run.complaints))

    caught = run.score.get("caught")
    return gate(True, f"the property discriminates: it caught {caught} of the broken versions of "
                      f"this policy that were tried")


def stage_check(run: Run, _: str) -> str:
    """The checks, run. Two invocations because `--property` REPLACES the derived questions."""
    run.rules = repair.run_checker(run.policy, event_schema=run.event_schema)
    run.prop = repair.check_property(run.policy, run.module_path, event_schema=run.event_schema)

    lines = [f"Policy: {run.policy.name}", f"Property: {run.module_name}", ""]
    if run.prop.get("_failed"):
        lines.append(f"The property could not be checked: {run.prop.get('_why')}")
    else:
        lines.append("The stated property HOLDS." if run.prop.get("held")
                     else "The stated property is BROKEN.")
        for v in run.prop.get("violations") or []:
            lines.append(f"  {v['invariant']} is violated at {v['state']}")

    # THE BOUND, in the same breath as the verdict. "Holds" on its own is the most overclaimable
    # sentence this pipeline produces: a property ranges over exactly what it names, and nothing
    # in a TLC verdict says how little that might be.
    lines += ["", "WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the "
              "states it ranges over its condition applies to:", "", run.explained.strip(), "",
              "This says nothing about requests the property does not name."]

    findings = [f for f in (run.rules.get("rules") or []) if f.get("finding")]
    lines += ["", f"Derived findings: {len(findings)}"]
    lines += [f"  {f.get('rule')}: {f.get('finding')}" for f in findings]
    run.checked = "\n".join(lines)
    return run.checked


def stage_report(run: Run, said: str) -> str:
    """findings.md, on every path -- including both rejections.

    Reached from three places and it has to read as one document from any of them, which is why it
    consults `Run` rather than whatever its parent happened to say.
    """
    run.out.mkdir(parents=True, exist_ok=True)
    run.findings = run.out / "findings.md"

    lines = [f"# {run.policy.name}", "", f"**Stated intention.** {run.intent}", ""]
    if run.round > 1 or run.exhausted:
        lines += [f"*Drafted in {run.round} of {run.rounds} attempt(s)"
                  + (", and the allowance ran out -- what follows is the last attempt, judged by "
                     "the same gates as any other." if run.exhausted else ".") + "*", ""]
    if run.rejected_at:
        lines += [f"## No property was checked: the draft was rejected at `{run.rejected_at}`", "",
                  "The gate below is a criterion in code, not a judgement a model was asked to "
                  "make. Nothing downstream ran, and nothing here was verified.", ""]
        lines += [f"- {c}" for c in run.complaints]
    else:
        # `said` is what the ANSWERER said -- report's parent on this path. The verdicts it was
        # answering from are read off Run, because they are the record and its prose is not.
        run.answered = unframe(said)
        lines += ["## What was checked", "", f"`{run.module_name}.tla`, drafted from the "
                  f"intention above and kept only because it caught "
                  f"{run.score.get('caught')} broken version(s) of this policy.", "",
                  "## Verdicts", "", "```", run.checked.strip(), "```", "",
                  "## Reported", "", run.answered]

    lines += ["", "---", "", "*A property drafted by a model and gated by Anchor. Findings "
              "against an agent-authored property are weaker evidence than findings against one "
              "a person wrote.*", ""]

    run.findings.write_text("\n".join(lines), encoding="utf-8")
    return f"wrote {run.findings}"


# ------------------------------------------------------------------------------------------------
def computed(run: Run, fn, name: str) -> Agent:
    return Agent(model=Computed(run, fn), callback_handler=None, name=name)


def build(run: Run, drafter: Agent | None = None, answerer: Agent | None = None, *,
          max_node_executions: int | None = None, node_timeout: float | None = None):
    """The graph. `gated` from tests/strands/anchor_workflow.py, wired to the real stages.

    The two agents are injected so the pipeline can be exercised without a provider -- and so that
    they are visibly two objects. `GraphBuilder` refuses one instance as two nodes, which is the
    separation enforced rather than intended.
    """
    if drafter is None or answerer is None:
        from agent.policy_agent import build_model                     # noqa: PLC0415
        # TWO models, deliberately built twice. Sharing one object would share whatever state it
        # carries, and the separation this graph exists for is about what the answerer has seen.
        drafter = drafter or Agent(model=build_model(), callback_handler=None,
                                   system_prompt=author.DRAFTER_PROMPT, name="draft")
        answerer = answerer or Agent(model=build_model(), callback_handler=None,
                                     system_prompt=ANSWERER_PROMPT, name="answer")

    preflight_ok, preflight_no = verdict("preflight")
    score_ok, score_no = verdict("score")

    # THE SEPARATION, asserted here because the graph no longer gets it free. While `draft` was
    # the drafting Agent itself, GraphBuilder refused one instance as two nodes; now that the
    # retry loop wraps it, the drafter is not a node and nobody else is checking.
    if drafter is answerer:
        raise ValueError("the agent that drafts the property cannot be the agent that reports on "
                         "it: asked for both, a model finds a trivial property the cheapest way "
                         "to pass, and a reporter that wrote the claim is not reviewing it")

    b = GraphBuilder()
    # A BACKSTOP, and it must never be what stops this run. Hitting it is not a graceful finish:
    # the executor sets status FAILED and returns from the batch loop (graph.py:787), so `report`
    # never runs and there is no findings.md -- the precise outcome `AlwaysReports` exists to
    # forbid. So the cap is set above what the graph can possibly use, and the thing that actually
    # bounds the work is `rounds`, inside `draft`, where running out still routes to `report`.
    #
    # Deliberately NOT set_execution_timeout: the `score` gate runs TLC once per mutant, and a
    # wall-clock bound would turn a slow-but-correct check into a stopped run with no report, for
    # the same reason. `author.score` carries its own timeout, where what is being timed is known.
    b.set_max_node_executions(max_node_executions or len(STAGES) * 2)
    if node_timeout is not None:
        b.set_node_timeout(node_timeout)

    b.add_node(computed(run, stage_describe, "describe"), "describe")
    b.add_node(computed(run, lambda r, t: stage_draft(r, t, drafter), "draft"), "draft")
    b.add_node(computed(run, stage_preflight, "preflight"), "preflight")
    b.add_node(computed(run, stage_score, "score"), "score")
    b.add_node(computed(run, stage_check, "check"), "check")
    b.add_node(answerer, "answer")
    b.add_node(computed(run, stage_report, "report"), "report")

    b.add_edge("describe", "draft")
    b.add_edge("draft", "preflight")
    b.add_edge("preflight", "score", condition=preflight_ok)
    b.add_edge("preflight", "report", condition=preflight_no)
    b.add_edge("score", "check", condition=score_ok)
    b.add_edge("score", "report", condition=score_no)
    b.add_edge("check", "answer")
    b.add_edge("answer", "report")
    b.set_entry_point("describe")
    return b.build()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("policy", type=Path)
    p.add_argument("--intent", required=True,
                   help="the requirement to state formally. Prose the POLICY did not write")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--event-schema", type=Path, default=None)
    p.add_argument("--mutants", type=int, default=8)
    p.add_argument("--name", default="Intent", help="the property module's name")
    p.add_argument("--rounds", type=int, default=3,
                   help="drafting attempts. A round costs one model call plus ~1s of SANY; "
                        "running out still reports (default: 3)")
    p.add_argument("--max-node-executions", type=int, default=None,
                   help="backstop on total node executions. Hitting it STOPS THE RUN WITH NO "
                        "REPORT, so it is set above what the graph can use; lower it only to "
                        "observe that behaviour")
    p.add_argument("--node-timeout", type=float, default=None,
                   help="per-node seconds. A node that times out fails, and a failed node "
                        "fail-fasts the whole run -- so this too can end a run with no report. "
                        "`score` runs TLC per mutant and is the one that would hit it")
    p.add_argument("--verbose", action="store_true",
                   help="leave third-party logging alone; see the note below")
    args = p.parse_args()

    if not args.verbose:
        # google-genai warns, once per process, that strands calls generate_content_stream
        # directly rather than through AsyncChat. It is advice to the SDK that wraps it, not to
        # anything a reader of this output can act on, and it lands in the middle of a report.
        #
        # Quieted HERE and not at import: this is the command line's choice about its own
        # stdout, and a library that imports `pipeline` keeps whatever logging it configured.
        import logging                                                 # noqa: PLC0415
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)

    run = Run(policy=args.policy, intent=args.intent,
              out=args.out or args.policy.parent / "anchor",
              event_schema=args.event_schema, module_name=args.name, mutants=args.mutants,
              rounds=args.rounds)

    graph = build(run, max_node_executions=args.max_node_executions,
                  node_timeout=args.node_timeout)
    result = graph(f"State and check the intention for {args.policy.name}.")

    ran = [n.node_id for n in result.execution_order]
    print(f"\nran {len(ran)}/{result.total_nodes}: {', '.join(ran)}", file=sys.stderr)
    if run.findings:
        print(run.findings)
    # A rejected draft is a complete run with nothing verified, and that is not a success.
    return 1 if run.rejected_at else 0


if __name__ == "__main__":
    sys.exit(main())
