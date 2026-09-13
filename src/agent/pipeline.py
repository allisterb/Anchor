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


def build(run: Run, drafter: Agent | None = None, answerer: Agent | None = None):
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

    b = GraphBuilder()
    # A REAL BOUND, not a way to quiet the warning GraphBuilder logs when there is none. Its
    # concern is a cycle running forever, and this graph is acyclic today -- but a retry round is
    # the obvious next change here, and a retry IS a cycle. Twice the stage count leaves room for
    # one and still stops.
    #
    # Deliberately NOT set_execution_timeout: the `score` gate runs TLC once per mutant, a wall
    # clock bound would turn a slow-but-correct check into a failed node, and fail-fast would take
    # the whole run down with it. `author.score` carries its own timeout, where the thing being
    # timed is known.
    b.set_max_node_executions(len(STAGES) * 2)
    b.add_node(computed(run, stage_describe, "describe"), "describe")
    b.add_node(drafter, "draft")
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
              event_schema=args.event_schema, module_name=args.name, mutants=args.mutants)

    graph = build(run)
    result = graph(f"State and check the intention for {args.policy.name}.")

    ran = [n.node_id for n in result.execution_order]
    print(f"\nran {len(ran)}/{result.total_nodes}: {', '.join(ran)}", file=sys.stderr)
    if run.findings:
        print(run.findings)
    # A rejected draft is a complete run with nothing verified, and that is not a success.
    return 1 if run.rejected_at else 0


if __name__ == "__main__":
    sys.exit(main())
