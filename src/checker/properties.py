"""Model-check an arbitrary Dogwood policy file for vacuity, one permit at a time.

    python src/checker/properties.py tests/policies/approval_gate_response.dw

A permit is VACUOUS when no session can make it grant anything. That is not a weak control, it is
zero control, and nothing about the policy's text says so -- it parses, it validates, and it
authorizes nothing. AWS's own material says the automated-reasoning tools Cedar provides do not
answer this for the temporal part of the language.

WHAT MAKES THIS MORE THAN A DEMO. Nobody hand-writes a model of the policy. The `.dw` text goes
through `translator` -- the parser whose reading agrees with the reference implementation on 914
recorded corpus pairs -- into a generated `PolicyUnderTest.tla`, and `Vacuity.tla` evaluates it with
`DogwoodSemantics!Decide`, the same evaluator validated against those pairs and against the live
engine on the `error`-event scenarios.

    any .dw ──> translator  ──> PolicyUnderTest.tla ──┐
                                                        ├──> TLC, once per permit
                              Vacuity.tla ──────────────┘

READ THE RESULT BACKWARDS. TLA+ has no `EF`, so reachability is asked by checking the negation and
reading the counterexample as the witness. A TLC *violation* means the permit CAN grant -- the good
outcome. A clean run means it never does. This script inverts that before printing, because the raw
reading is a trap.

The bound is real: VACUOUS means "no session of up to `--attempts` attempts makes it fire", not
"never". Raise it to trade runtime for confidence.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"

sys.path.insert(0, str(REPO / "src"))

from translator import (DECISION_KIND, Unsupported, apply_pins,  # noqa: E402
                        generate_policy_module, parse_policies, parse_schema, run_tlc,
                        stamp_keys, vocabulary)

# Event kinds AgentCore records. `request` is the decision event -- the point authorization runs --
# and the outcome is `response` when the action completed, `error` when it was denied.


# ---------------------------------------------------------------------------- checking
CONFIG = """SPECIFICATION Spec

\\* A session ends after MaxAttempts, which has no successor action.
CHECK_DEADLOCK FALSE

CONSTANTS
    MaxAttempts = {attempts}
    MaxAmount = {amount}
    Target = {target}

INVARIANT TypeOK

\\* MEANT TO FAIL. A violation is the witness session; a clean run means there is none.
\\* See the header of Vacuity.tla for why the reading is inverted.
INVARIANT {invariant}
"""


def check_one(work: Path, target: int, attempts: int, amount: int,
              invariant: str = "NeverFires") -> tuple[bool, str]:
    """Returns (a witness exists, TLC output). Raises if TLC could not answer.

    `NeverFires`   a witness means the permit CAN grant something -- it is live.
    `NeverMatters` a witness means deleting the rule WOULD change a verdict -- it is load-bearing.
    """
    (work / "Vacuity.cfg").write_text(
        CONFIG.format(attempts=attempts, amount=amount, target=target, invariant=invariant),
        encoding="utf-8")

    ok, out = run_tlc("Vacuity", work, work)

    if f"Invariant {invariant} is violated" in out:
        return True, out
    if ok and "Model checking completed" in out:
        return False, out

    # Anything else -- a parse error, an unsupported construct reaching TLC, a TypeOK failure --
    # is not an answer. Never let it read as "vacuous"; that is the silent-wrong-answer direction.
    raise RuntimeError(f"TLC could not answer for permit {target}:\n{out}")


def witness(out: str) -> str:
    """The session TLC found, as the actions attempted in order.

    Only the LAST state block is scanned. TLC prints the whole `trace` variable at every state, so
    each event appears once more for every state that follows it -- reading the full output turns a
    two-attempt witness into "Approve -> Approve -> Trade" and overstates what it took to fire.
    """
    states = re.split(r"^State \d+: ", out, flags=re.MULTILINE)
    final = states[-1] if len(states) > 1 else out
    actions = re.findall(r'action \|-> "([A-Za-z0-9_]+)",\s*kind \|-> "' + DECISION_KIND + '"', final)
    return " -> ".join(actions) if actions else "(see TLC output, --verbose)"


# ---------------------------------------------------------------------------- custom properties
def prove(args, policies: list[dict], vocab: dict, keys: list[str] | None = None) -> int:
    """Check the author's claim about what this policy means."""
    print(f"{args.policy.name} against {args.property_module.name}: "
          f"{len(policies)} rule(s)\n")

    with tempfile.TemporaryDirectory(prefix="anchor-prove-") as tmp:
        work = Path(tmp)
        (work / "PolicyUnderTest.tla").write_text(
            generate_policy_module(args.policy, policies, vocab, keys=keys), encoding="utf-8")
        shutil.copyfile(SPECS / "DogwoodSemantics.tla", work / "DogwoodSemantics.tla")

        held, out = check_property(work, args.property_module)

    if held:
        print("  every claim holds over every request the property names.\n")
        print("That is not a proof about requests it does not name. A property ranges over what it\n"
              "says it ranges over, and nothing warns you when that is less than you meant.")
        return 0

    for v in violated_by(out) or ["TLC could not answer:\n" + out[-1200:]]:
        print(f"  BROKEN  {v}")
    print("\nThe policy does not mean what the property says it means. The state above is the\n"
          "request that breaks the claim.")
    return 1


# ---------------------------------------------------------------------------- diff
def diff(args, policies: list[dict], other: list[dict], vocab: dict,
         keys: list[str] | None = None) -> int:
    """Is there a session the two files decide differently?

    Target = 0 selects `Other` as the set compared against, so this is one TLC run rather than
    one per rule. A violation of `NeverMatters` is the witness session.
    """
    print(f"{args.policy.name} vs {args.against.name}: "
          f"{len(policies)} rule(s) vs {len(other)}, bound {args.attempts} attempts\n")

    with tempfile.TemporaryDirectory(prefix="anchor-diff-") as tmp:
        work = Path(tmp)
        (work / "PolicyUnderTest.tla").write_text(
            generate_policy_module(args.policy, policies, vocab, other, args.against.name, keys),
            encoding="utf-8")
        for module in ("Vacuity.tla", "DogwoodSemantics.tla"):
            shutil.copyfile(SPECS / module, work / module)

        differs, out = check_one(work, 0, args.attempts, args.amount, "NeverMatters")

        if args.verbose:
            print("\n".join(f"    {line}" for line in out.splitlines()))

    if differs:
        print(f"  THEY DIFFER   witness: {witness(out)}\n")
        print("A session exists that the two files decide differently. The witness above is the\n"
              "sequence of attempts that reaches it -- run with --verbose for the full trace,\n"
              "which shows the decision where they part company.")
        return 0

    print(f"  no difference   no session of up to {args.attempts} attempts tells them apart\n")
    print("Within the bound the two files are interchangeable: every request either set allows,\n"
          "the other allows too. That is a statement about DECISIONS, not about text -- the files\n"
          "may well read very differently.")
    return 0


# ---------------------------------------------------------------------------- custom properties
def check_property(work: Path, module: Path) -> tuple[bool, str]:
    """Run the author's own property module against the generated policy records.

    Returns (it holds, TLC output). A violation is the ANSWER here, not an inversion: unlike the
    vacuity questions, which ask for reachability and so read a counterexample as the witness, a
    property is meant to hold and TLC's counterexample names the request that breaks it.
    """
    cfg = module.with_suffix(".cfg")
    if not cfg.exists():
        raise Unsupported(
            f"{module.name} needs a companion {cfg.name} naming the invariants to check, e.g.\n"
            f"      SPECIFICATION Spec\n"
            f"      INVARIANT YourClaim\n"
            f"    Naming them is deliberate: a property nobody listed is a property nobody checked")

    shutil.copyfile(module, work / module.name)
    shutil.copyfile(cfg, work / cfg.name)
    return run_tlc(module.stem, work, work)


def violated_by(out: str) -> list[str]:
    """The invariants that failed, with the state that broke each."""
    found = []
    for i, line in enumerate(out.splitlines()):
        if "is violated" in line:
            state = [l.strip() for l in out.splitlines()[i + 1:i + 6] if l.strip().startswith("req")]
            found.append(f"{line.split('Error: ')[-1].strip()}"
                         + (f"{chr(10)}      {state[0]}" if state else ""))
    return found


# ---------------------------------------------------------------------------- entry
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("policy", type=Path, help="a .dw policy file")
    ap.add_argument("--against", type=Path, metavar="OTHER.dw",
                    help="a second .dw file: report a session the two decide differently, "
                         "rather than checking each rule")
    ap.add_argument("--attempts", type=int, default=3, help="session length bound (default 3)")
    ap.add_argument("--amount", type=int, default=2,
                    help="numeric domain for input fields, 1..N (default 2)")
    ap.add_argument("--max-fields", type=int, default=4, metavar="N",
                    help="refuse a policy reading more than N input/output fields. The"
                         " request space is the product of their domains, so this bounds"
                         " state space rather than soundness (default 4)")
    ap.add_argument("--property", type=Path, metavar="FILE.tla", dest="property_module",
                    help="a TLA+ module of your own, extending PolicyUnderTest, stating what the "
                         "policy is supposed to mean. Needs a companion .cfg naming its invariants")
    ap.add_argument("--event-schema", type=Path, metavar="FILE.dwschema",
                    help="the event schema the policy is deployed under. Without it every answer "
                         "assumes the UNPINNED reading, which is not the shipped default")
    ap.add_argument("--verbose", action="store_true", help="print the TLC output for each permit")
    args = ap.parse_args()

    for f in (args.policy, args.against):
        if f is not None and not f.exists():
            print(f"no such policy file: {f}", file=sys.stderr)
            return 2

    try:
        policies = parse_policies(args.policy.read_text(encoding="utf-8"))
        other = parse_policies(args.against.read_text(encoding="utf-8")) if args.against else None

        # The event schema, which decides what the policy MEANS before anything is checked about
        # what it says. Both halves, and they are different jobs: a partial pin becomes an
        # ordinary conjunct, a universal one a partition key stamped onto every term.
        schema = ({"keys": [], "partial": {}} if args.event_schema is None
                  else parse_schema(args.event_schema.read_text(encoding="utf-8")))
        for rules in (policies, other):
            if rules is not None:
                apply_pins(rules, schema)
                if schema["keys"]:
                    stamp_keys(rules, schema["keys"])
        # The vocabulary must span BOTH files. A version that adds a permit for an action the
        # other never mentions would otherwise never have that action attempted, and the run
        # would report "no difference" having not looked -- the one wrong answer that matters.
        vocab = vocabulary(policies + (other or []), args.amount, args.max_fields)
    except Unsupported as e:
        # The house rule: refuse rather than approximate. A translator that quietly mishandles a
        # construct produces a verdict nobody can attribute.
        print(f"REFUSED: {args.policy.name} is outside the modelled subset\n  {e}", file=sys.stderr)
        return 2

    # Say which reading produced the answers. Leaving it implicit is how a verdict computed for
    # `unpinned` gets read as one for the deployed configuration.
    if schema["keys"]:
        print(f"under {args.event_schema.name}: partitioned by "
              f"{', '.join(schema['keys'])} -- a temporal predicate sees only its own partition\n")
    elif args.event_schema is not None:
        print(f"under {args.event_schema.name}: no universal pin, so global-trace semantics\n")
    else:
        print("no --event-schema given, so every answer below assumes the UNPINNED reading\n"
              "  (global trace). The shipped DEFAULT partitions by principal, under which a rule\n"
              "  reported live here may never fire.\n")

    if args.property_module is not None:
        return prove(args, policies, vocab, schema["keys"])

    if args.against is not None:
        return diff(args, policies, other, vocab, schema["keys"])

    permits = [i + 1 for i, p in enumerate(policies) if p["effect"] == "permit"]
    forbids = [i + 1 for i, p in enumerate(policies) if p["effect"] == "forbid"]

    print(f"{args.policy.name}: {len(permits)} permit(s), {len(forbids)} forbid(s), "
          f"bound {args.attempts} attempts\n")

    if not policies:
        print("nothing to check -- the file declares no rules")
        return 0

    findings = []
    with tempfile.TemporaryDirectory(prefix="anchor-vacuity-") as tmp:
        work = Path(tmp)
        (work / "PolicyUnderTest.tla").write_text(
            generate_policy_module(args.policy, policies, vocab, keys=schema["keys"]), encoding="utf-8")
        for module in ("Vacuity.tla", "DogwoodSemantics.tla"):
            shutil.copyfile(SPECS / module, work / module)

        for i, rule in enumerate(policies, 1):
            shown = " | ".join(rule["actions"]) or "(any)"
            label = f'{rule["effect"]} #{i}  action == {shown}'

            # Does deleting this rule change any verdict? One question, both shapes: a forbid
            # that never denies, and a permit some other permit always covers.
            matters, out = check_one(work, i, args.attempts, args.amount, "NeverMatters")

            # For a permit, ask the sharper question too. Vacuous implies redundant, so a
            # permit reported vacuous is also deletable -- but "never fires at all" is a more
            # useful thing to be told than "something else covers it".
            fires = None
            if rule["effect"] == "permit":
                fires, fout = check_one(work, i, args.attempts, args.amount, "NeverFires")
                if fires:
                    out = fout

            if rule["effect"] == "permit" and not fires:
                verdict, note = "VACUOUS", f"no session of up to {args.attempts} attempts makes it grant"
            elif not matters:
                verdict = "REDUNDANT" if rule["effect"] == "permit" else "DEAD"
                note = "deleting it changes no verdict in any session"
            else:
                verdict, note = "live", f"witness: {witness(out)}"

            findings.append((i, rule["effect"], verdict))
            print(f"  {label:34} {verdict:10}{note}")

            if args.verbose:
                print("\n".join(f"      {line}" for line in out.splitlines()))

    print()
    dead = [(i, e, v) for i, e, v in findings if v != "live"]
    if dead:
        for i, effect, verdict in dead:
            print(f"{verdict} {effect} #{i}")
        print()
        print("A rule that changes no verdict can be deleted, and a policy set is easier to reason")
        print("about the fewer of them it has.")

        # Only the verdicts actually reported. Explaining one that did not occur is noise, and it
        # also makes the output awkward to assert on.
        seen = {v for _, _, v in dead}
        legend = {
            "VACUOUS": ("  VACUOUS    the permit never fires at all -- whatever it was meant to\n"
                        "             allow is unreachable, a bug rather than untidiness"),
            "REDUNDANT": "  REDUNDANT  it fires, but another permit always would too",
            "DEAD": "  DEAD       the forbid never denies anything the rest of the set would allow",
        }
        for verdict in ("VACUOUS", "REDUNDANT", "DEAD"):
            if verdict in seen:
                print(legend[verdict])
    else:
        print(f"every rule is load-bearing within {args.attempts} attempts.\n"
              "That is not a proof of correctness -- only that none of them is inert.")

    # Vacuity is a finding, not an error. The exit code says whether the run ANSWERED.
    return 0


if __name__ == "__main__":
    sys.exit(main())
