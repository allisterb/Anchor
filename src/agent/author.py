"""Draft a property module from a stated intention -- and refuse to keep one that says nothing.

    python src/agent/author.py examples/aws1/07-trust-decay.dw \\
        --intent "After 15 minutes without advisor interaction, the agent loses write access."

THE HAZARD THIS IS BUILT AROUND, stated before the feature: a property an agent derives from the
POLICY is a restatement of the policy. Checking a policy against its own restatement always passes
and establishes nothing, and it is the most-reported pathology in agentic verification -- asked to
produce both an artifact and its specification, a model finds that a trivial specification is the
cheapest way to pass. `ensures TRUE` holds of everything.

So two things, and neither is optional:

    THE INTENT COMES FROM SOMEWHERE ELSE.  `--intent` is prose the policy did not write: a
                                           requirement, a comment, an article's sentence, what the
                                           person actually asked for. Autoformalising a REQUIREMENT
                                           is a different act from summarising a rule, and only the
                                           first can disagree with the policy.

    THE DRAFT MUST DISCRIMINATE.           A property is kept only if it either fails on the policy
                                           as written -- in which case it has already shown it can
                                           tell one policy from another -- or, holding, catches at
                                           least one MUTANT: a version of the policy broken in a
                                           small way. A property true of the policy and of every
                                           broken version of it is not constraining anything.

WHAT COMES OUT IS A DRAFT. It is a formal statement of somebody's prose, written by a model, and
whether it captures what they meant is exactly the question no tool answers. Findings against an
agent-authored property are weaker evidence than findings against one a person wrote, and anything
reporting them should say which it has.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

CHECKER = REPO / "src" / "checker" / "properties.py"

WEAK_PROPERTY = 4   # properties.py: holds, but catches no mutant

INVARIANT_LINE = re.compile(r"^INVARIANT\s+(\w+)", re.MULTILINE)


@dataclass
class Draft:
    """One attempt at a property module, and what the checker made of it."""

    number: int
    module: str
    config: str
    accepted: bool = False
    complaints: list[str] = field(default_factory=list)
    holds: bool | None = None
    caught: int | None = None
    output: str = ""

    def feedback(self) -> str:
        return "\n".join(f"- {c}" for c in self.complaints)


@dataclass
class AuthorRun:
    drafts: list[Draft] = field(default_factory=list)
    accepted: Draft | None = None


def describe(policy: Path, event_schema: Path | None = None) -> dict:
    """The vocabulary a property module may name, from the checker itself.

    NOT GUESSED AND NOT ASKED OF THE MODEL. The actions, field names and value domains come from
    the policy's own text, and a module naming anything else does not compile. Handing the model
    the real vocabulary is the difference between drafting and inventing.
    """
    args = [sys.executable, str(CHECKER), str(policy), "--describe"]
    if event_schema is not None:
        args += ["--event-schema", str(event_schema)]
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=300)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"_failed": True, "_why": (proc.stderr or proc.stdout).strip()[-1200:]}


def score(policy: Path, module: Path, *, event_schema: Path | None = None,
          mutants: int = 8, timeout: int = 3600) -> dict:
    """Check a property AND ask whether it would notice the policy breaking.

    One invocation, because the two answers belong together: "it holds" is only reassuring
    alongside "and it would not have held of something broken".
    """
    args = [sys.executable, str(CHECKER), str(policy), "--property", str(module),
            "--mutation-score", "--mutants", str(mutants)]
    if event_schema is not None:
        args += ["--event-schema", str(event_schema)]
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    out = proc.stdout + proc.stderr

    caught = None
    if (m := re.search(r"^\s*(\d+) of (\d+) caught\.", out, re.MULTILINE)):
        caught = int(m.group(1))

    # 4 is "holds, but caught no mutant" -- it HOLDS, and `assess` below is what rejects it.
    # Reading 4 as a failure would have `assess` conclude the property discriminates, which is the
    # exact opposite of what exit 4 means, and would wave through the one draft the gate exists to
    # stop.
    return {"holds": proc.returncode in (0, WEAK_PROPERTY), "exitCode": proc.returncode,
            "caught": caught, "output": out.strip(),
            # A TLA+ module that will not parse is not a verdict about the policy. Distinguished
            # from a property that ran and failed, because the two need opposite responses.
            "ran": not any(n in out for n in ("Could not parse module", "AbortException",
                                    "Parsing or semantic analysis failed"))}


def assess(result: dict, config: str) -> list[str]:
    """Why this draft is not acceptable yet. Empty means it is."""
    complaints: list[str] = []

    if not result.get("ran"):
        complaints.append(
            "the module did not parse or did not run. TLC said:\n"
            + "\n".join(result.get("output", "").splitlines()[-12:]))
        return complaints

    if not INVARIANT_LINE.search(config):
        complaints.append("the .cfg names no INVARIANT, so nothing was checked. "
                          "List every claim you want checked.")
        return complaints

    # THE ADVERSARIAL GATE. A property that holds and catches nothing is true and empty.
    if result.get("holds") and result.get("caught") == 0:
        complaints.append(
            "the property HOLDS, but it also holds of every broken version of this policy that "
            "was tried -- rules deleted, permits turned into forbids, conditions dropped. So it "
            "is not constraining this policy at all. It is probably ranging over requests the "
            "policy never sees, or asserting something trivially true. State the claim about "
            "concrete actions and values the policy actually names.")

    return complaints


def author(policy: Path, intent: str, propose, *, rounds: int = 3,
           event_schema: Path | None = None, mutants: int = 8,
           out_dir: Path | None = None, module_name: str = "Intent",
           on_draft=None) -> AuthorRun:
    """Draft a property module for `intent`, and keep it only if it discriminates.

    `propose(vocabulary, intent, feedback) -> (module_text, config_text)`. Injected, so the loop
    and its gate are testable without a model -- the gate is the part that matters and the part
    that would rot silently.
    """
    vocab = describe(policy, event_schema)
    # The name the module must carry, because this loop is what chooses the file name and TLA+
    # requires the two to agree. Carried in the vocabulary so an injected proposer sees it too.
    vocab["requiredModuleName"] = module_name
    run = AuthorRun()
    feedback = ""

    out = out_dir or policy.parent
    out.mkdir(parents=True, exist_ok=True)
    module_path = out / f"{module_name}.tla"
    config_path = out / f"{module_name}.cfg"
    existing = (module_path.read_text(encoding="utf-8") if module_path.exists() else None,
                config_path.read_text(encoding="utf-8") if config_path.exists() else None)

    try:
        for n in range(1, rounds + 1):
            module, config = propose(vocab, intent, feedback)
            module_path.write_text(module, encoding="utf-8")
            config_path.write_text(config, encoding="utf-8")

            result = score(policy, module_path, event_schema=event_schema, mutants=mutants)
            complaints = assess(result, config)

            draft = Draft(number=n, module=module, config=config, accepted=not complaints,
                          complaints=complaints, holds=result.get("holds"),
                          caught=result.get("caught"), output=result.get("output", ""))
            run.drafts.append(draft)
            if on_draft:
                on_draft(draft)

            if draft.accepted:
                run.accepted = draft
                return run

            feedback = draft.feedback()
    finally:
        # Put back whatever was there if nothing was accepted. A rejected draft must not replace a
        # property somebody wrote by hand, and leaving the last failed attempt on disk is exactly
        # how that would happen.
        if run.accepted is None:
            for path, before in ((module_path, existing[0]), (config_path, existing[1])):
                if before is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(before, encoding="utf-8")

    return run


def model_author(model=None):
    """A drafter backed by a language model. The only part that costs money."""
    from strands import Agent

    from agent.policy_agent import build_model

    agent = Agent(model=model or build_model(), callback_handler=None, system_prompt=(
        "You write TLA+ property modules that state what a Dogwood authorization policy is "
        "SUPPOSED to mean, so that a model checker can test the policy against the claim.\n\n"
        "You are given the module's VOCABULARY as JSON -- the actions, event kinds, input and "
        "output fields with their value domains, and the constructors. Name only what is there; "
        "anything else will not compile.\n\n"
        # NOT JSON. TLA+ is backslash-heavy -- `\\*`, `\\/`, `\\in` -- and every one of those is an
        # invalid JSON escape, so a model embedding a module in a JSON string produces something
        # that will not parse however careful it is being. Delimiters have no escaping rules.
        "Return the two files separated by these exact markers and nothing else:\n\n"
        "===MODULE===\n"
        "<the complete .tla file text>\n"
        "===CONFIG===\n"
        "<the complete .cfg file text, naming every invariant with INVARIANT lines>\n\n"
        "The module must be named as instructed, EXTEND PolicyUnderTest, and state the claim as "
        "one or more named invariants. State the claim about concrete actions and values the "
        "policy actually names: a claim that ranges over nothing passes without checking "
        "anything, which is worse than failing."))

    # THE MANUAL WE ALREADY HAVE. `writing-a-property-module` is the article the MCP server serves
    # to any agent asking this question, and it carries the two things a drafter gets wrong on its
    # own: that a temporal claim needs a hand-built session, and that `time` is in seconds. Handed
    # over directly rather than left to be fetched -- this loop is not conversational, so there is
    # no turn in which to go and look it up.
    manual = (REPO / "src" / "Anchor.MCPServer" / "knowledge"
              / "writing-a-property-module.md").read_text(encoding="utf-8")

    def propose(vocab: dict, intent: str, feedback: str) -> tuple[str, str]:
        # THE MODULE NAME, said plainly and first. TLA+ requires the module name to match its file
        # name, this loop chooses the file name, and the skeleton in the vocabulary carries a
        # DIFFERENT name derived from the policy -- so a draft that copies the skeleton's header
        # is written to a file it does not match and fails to parse, with an error that mentions
        # neither. The system prompt said "named as instructed" and nothing did the instructing.
        required = vocab.get("requiredModuleName", "Intent")
        prompt = (f"The module MUST be named exactly `{required}`, so its first line is:\n"
                  f"    ---------------------------- MODULE {required} "
                  f"----------------------------\n"
                  f"Do not copy the module name from the skeleton below; it is a different name.\n\n"
                  f"How to write one:\n\n{manual}\n\n"
                  f"---\n\nThe vocabulary for THIS policy:\n\n"
                  f"```json\n{json.dumps(vocab, indent=2)[:8000]}\n```\n\n"
                  f"The intention to state formally:\n\n{intent}")
        if feedback:
            prompt += f"\n\nYour previous attempt was rejected:\n{feedback}\n\nTry again."

        text = str(agent(prompt)).strip()

        module, _, config = text.partition("===CONFIG===")
        module = module.partition("===MODULE===")[2] or module

        # Fences survive instructions not to use them, and stripping one here beats one more line
        # of prompt nobody can enforce.
        def unfence(s: str) -> str:
            s = s.strip()
            if s.startswith("```"):
                lines = s.splitlines()
                s = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return s.strip() + "\n"

        # A reply missing the markers is a failed draft, not a crash: the loop says so and asks
        # again, which is what it is for. The empty config is what `assess` will complain about.
        return unfence(module), unfence(config) if config.strip() else ""

    return propose


def show(draft: Draft) -> None:
    status = "ACCEPTED" if draft.accepted else "rejected"
    caught = "" if draft.caught is None else f", caught {draft.caught} mutant(s)"
    holds = {True: "holds", False: "does not hold", None: "no verdict"}[draft.holds]
    print(f"\n--- draft {draft.number}: {status} ({holds}{caught}) " + "-" * 28, file=sys.stderr)
    for c in draft.complaints:
        print(f"  {c}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("policy", type=Path, help="the .dw policy the claim is about")
    ap.add_argument("--intent", type=str, default=None,
                    help="what the policy is supposed to mean, in words. MUST come from outside "
                         "the policy -- a requirement, a comment, what somebody asked for")
    ap.add_argument("--intent-file", type=Path, default=None, help="the same, from a file")
    ap.add_argument("--name", type=str, default="Intent",
                    help="the module name, and so the file name (default: Intent)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="where to write the module (default: beside the policy)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--mutants", type=int, default=8,
                    help="how many broken versions of the policy to test the draft against")
    ap.add_argument("--event-schema", type=Path, default=None)
    args = ap.parse_args()

    intent = args.intent or (args.intent_file.read_text(encoding="utf-8")
                             if args.intent_file else None)
    if not intent:
        print("--intent or --intent-file is required: a property module states an INTENTION, and "
              "one derived from the policy itself would only restate it.", file=sys.stderr)
        return 2

    print(f"drafting {args.name}.tla for {args.policy.name}\n"
          f"up to {args.rounds} round(s); each one makes live model calls\n", file=sys.stderr)

    run = author(args.policy, intent, model_author(), rounds=args.rounds,
                 event_schema=args.event_schema, mutants=args.mutants,
                 out_dir=args.out_dir, module_name=args.name, on_draft=show)

    if run.accepted is None:
        print(f"\nNO USABLE DRAFT after {len(run.drafts)} round(s). Nothing was written.",
              file=sys.stderr)
        return 1

    out = (args.out_dir or args.policy.parent) / f"{args.name}.tla"
    print(f"\nwrote {out} and its .cfg", file=sys.stderr)
    print("\nTHIS IS A DRAFT. It is a formal statement of your prose, written by a model, and\n"
          "whether it captures what you meant is the one question no tool here answers. Read it\n"
          "before trusting a finding that rests on it.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
