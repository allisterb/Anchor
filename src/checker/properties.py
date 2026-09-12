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
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"

sys.path.insert(0, str(REPO / "src"))

from translator import (DECISION_KIND, DEFAULT_MAX_WINDOW, Unsupported, apply_pins,  # noqa: E402
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
              invariant: str = "NeverFires",
              smoke: int | None = None) -> tuple[bool | None, str]:
    """Returns (a witness exists, TLC output). Raises if TLC could not answer.

    `NeverFires`   a witness means the permit CAN grant something -- it is live.
    `NeverMatters` a witness means deleting the rule WOULD change a verdict -- it is load-bearing.

    THREE answers, not two:

        True   a witness was found. SOUND either way -- a witness is a witness however it was
               reached, so a smoke run that finds one has settled the question.
        False  no witness EXISTS. Only exhaustive search can say this.
        None   no witness was found by a random walk, which says nothing about whether one exists.

    `smoke` is a number of random behaviours. It can only ever return True or None, because the
    claims False supports -- VACUOUS, REDUNDANT, DEAD -- are claims of ABSENCE, and a random walk
    cannot establish absence. Reporting one from a smoke run would be the silent-wrong-answer
    direction, and it would tell someone to delete a working rule.
    """
    (work / "Vacuity.cfg").write_text(
        CONFIG.format(attempts=attempts, amount=amount, target=target, invariant=invariant),
        encoding="utf-8")

    # A fixed seed, so a verdict is reproducible. TLC randomises the seed by default, which would
    # make `unknown` mean something different on every run and a reported witness unreproducible.
    extra = ["-simulate", f"num={smoke}", "-seed", "0"] if smoke else None
    ok, out = run_tlc("Vacuity", work, work, extra)

    if f"Invariant {invariant} is violated" in out:
        return True, out
    if ok and "Model checking completed" in out:
        return False, out

    # Simulation ran to the end of its budget and found nothing. Positive evidence that it RAN --
    # not merely the absence of a violation -- so a crash cannot arrive here dressed as "unknown".
    if smoke and ok and "Random Simulation" in out and "Finished in" in out:
        return None, out

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



# ---------------------------------------------------------------------------- describe
KIND_NAMES = {"s": "string", "n": "integer", "b": "boolean", "a": "address"}

# The string `field_domain` appends so that "does not match" is reachable. A NUL byte, chosen so it
# cannot collide with a real value -- which also makes it something no author can type. It is
# DESCRIBED below, never offered as a literal to write.
UNNAMED = "\u0000none"


def writable(domain: list) -> list:
    """The domain without the sentinel."""
    return [(k, v) for k, v in domain if not (k == "s" and v == UNNAMED)]


def constructor(kind: str, value) -> str:
    """One value as a property module must WRITE it. `22` is not a value here; `Num(22)` is."""
    if kind == "b":
        return f'Bool({"TRUE" if value else "FALSE"})'
    if kind == "n":
        return f"Num({value})"
    if kind == "a":
        return f'Addr({", ".join(str(o) for o in value)})'
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'Str("{escaped}")'


def skeleton(name: str, policies: list[dict], vocab: dict) -> str:
    """A property module that compiles and checks something, for the author to edit.

    Deliberately not a stub with holes. A skeleton that does not run teaches nothing about whether
    the harness is wired correctly, and the wiring -- EXTENDS, the INSTANCE, the shape of Decide's
    arguments -- is the part nobody can guess.
    """
    action = sorted(vocab["actions"])[0] if vocab["actions"] else "Act"
    fields = sorted(vocab["input"])

    if fields:
        # Named explicitly rather than drawn from InputDomain: see the warning below. The sentinel
        # is dropped -- it exists to make non-matching reachable inside the model, and an author
        # who wants that here writes a value of their own.
        sets = "\n".join(
            f'{f}Values == {{' + ", ".join(constructor(k, v)
                                           for k, v in writable(vocab["domains"][("input", f)])) + "}"
            for f in fields)
        binds = ", ".join(f"{f} \\in {f}Values" for f in fields)
        rec = ", ".join(f"{f} |-> {f}" for f in fields)
        requests = f"{sets}\n\nRequests == {{[{rec}] : {binds}}}"
        claim = (f"\\* EDIT THIS. It says the policy grants every request named above, which is\n"
                 f"\\* almost certainly not what {name}.dw means.\n"
                 f"EverythingIsGranted == Grants(req)")
    else:
        requests = ('\\* This policy reads no input fields, so one request is the whole space.\n'
                    'Requests == {[f \\in {} |-> Str("")]}')
        claim = "EverythingIsGranted == Grants(req)"

    return f"""---------------------------- MODULE {name} ----------------------------
\\* What {name}.dw is SUPPOSED to mean, stated by its author. The three built-in findings
\\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the
\\* other kind, and only the author can write it.
\\*
\\* Check it with:  python src/checker/properties.py {name}.dw --property {name}.tla
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

D == INSTANCE DogwoodSemantics WITH Cases <- << >>

\\* The verdict for one request. No session: "what does this policy decide for this request" is
\\* not a temporal question, so there is no state machine beyond holding one request still.
Grants(input) == D!Decide(<<Request("{action}", input)>>, Policies, 1, AllValues)

(***************************************************************************)
(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)
(*                                                                         *)
(* Written out rather than derived from InputDomain, and that is the       *)
(* point. A space derived from the policy's own literals cannot test a     *)
(* claim about a value the policy never mentions: delete the rule that     *)
(* names a value and it vanishes from the vocabulary, so the claim ranges  *)
(* over nothing and PASSES having looked at nothing.                       *)
(*                                                                         *)
(* Add the values your claim is about, including ones this policy never    *)
(* mentions.                                                               *)
(***************************************************************************)
{requests}

\\* One request, chosen nondeterministically and held, so a violation's counterexample NAMES the
\\* request that breaks the claim rather than merely reporting that one exists.
VARIABLE req
Init == req \\in Requests
Next == UNCHANGED req
Spec == Init /\\ [][Next]_req

(***************************************************************************)
(* THE CLAIM.                                                              *)
(***************************************************************************)
{claim}

=============================================================================
"""


def describe(args, policies: list[dict], vocab: dict, schema: dict, reading: str) -> int:
    """Everything a property module may name, as JSON, plus a skeleton that already runs."""
    name = args.policy.stem

    def side(which):
        out = []
        for f in sorted(vocab[which]):
            domain = vocab["domains"][(which, f)]
            kept = writable(domain)
            out.append({
                "name": f,
                "kind": KIND_NAMES.get(domain[0][0], "unknown"),
                "domain": [constructor(k, v) for k, v in kept],
                # The model admits one more value than the policy names, so that a condition
                # failing to match is reachable. Not writable -- for a string it is a NUL byte --
                # so it is reported rather than offered.
                "plusOneValueThePolicyNeverNames": len(kept) != len(domain),
            })
        return out

    doc = {
        "source": args.policy.name,
        "reading": reading,
        "module": "PolicyUnderTest",
        "actions": sorted(vocab["actions"]),
        "kinds": sorted(vocab["kinds"] | {DECISION_KIND}),
        "decisionKind": DECISION_KIND,
        "inputFields": side("input"),
        "outputFields": side("output"),
        "pinKeys": schema["keys"],
        "rules": [{"index": i, "effect": p["effect"], "actions": p["actions"] or ["(any)"]}
                  for i, p in enumerate(policies, 1)],
        "operators": {
            "Request(action, input)": "one request as the evaluator reads it",
            "Policies": "the rule set, as the sequence Decide evaluates",
            "AllValues": "every value any field may take -- Decide's last argument",
            "InputDomain": "[field |-> {values}] for the fields above",
            "OutputDomain": "[field |-> {values}] for the output fields",
            "PinKeys": "the fields a universal pin partitions on; empty means global-trace",
        },
        "constructors": {
            "Str(x)": "a string",
            "Num(x)": "an integer",
            "Bool(x)": "TRUE or FALSE",
            "Addr(a, b, c, d)": "an address, FOUR OCTETS -- TLC works in Java ints, so "
                                "208.4.4.0 as 3489924096 is not a value it can hold",
            "Anon": "the anonymous principal/resource/session a per-request claim uses",
        },
        "rules_for_writing_one": [
            "EXTENDS PolicyUnderTest, and instantiate DogwoodSemantics with Cases <- << >>.",
            "Scalars are TAGGED. Write Num(22), never 22 -- TLC refuses a cross-kind comparison "
            "rather than quietly answering one.",
            "There is no Inputs. State the requests your claim is about, including values this "
            "policy never mentions, or the claim may range over nothing and pass.",
            "The .cfg must name SPECIFICATION Spec and every INVARIANT. A property nobody listed "
            "is a property nobody checked.",
        ],
        "skeleton": skeleton(name, policies, vocab),
        "config": ("SPECIFICATION Spec\n\n"
                   "\\* Naming the claims is deliberate. A property nobody listed is a property\n"
                   "\\* nobody checked.\n"
                   "INVARIANT EverythingIsGranted\n"),
    }
    print(json.dumps(doc, indent=2))
    return 0


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
    ap.add_argument("--smoke", type=int, metavar="N", nargs="?", const=1000,
                    help="run TLC as a random walk of N behaviours (default 1000) instead of "
                         "exhaustively. Reports `live` -- which is SOUND, a witness is a witness "
                         "however it was found -- or `unknown`. It can never report VACUOUS, "
                         "REDUNDANT or DEAD: those are claims of absence, and a random walk cannot "
                         "establish absence. For models too big to exhaust")
    ap.add_argument("--describe", action="store_true",
                    help="print, as JSON, what a --property module extending PolicyUnderTest may "
                         "name for this policy -- actions, fields, domains, constructors -- plus a "
                         "skeleton module that already runs. Checks nothing")
    args = ap.parse_args()

    for f in (args.policy, args.against):
        if f is not None and not f.exists():
            print(f"no such policy file: {f}", file=sys.stderr)
            return 2

    try:
        # Parsed twice over: once to read the schema's cap, then again under it. A policy
        # looking back further than the deployment allows is a validation error, so answering
        # questions about it would be answering about something undeployable.
        cap = (DEFAULT_MAX_WINDOW if args.event_schema is None
               else parse_schema(args.event_schema.read_text(encoding="utf-8"))["max_window"])
        policies = parse_policies(args.policy.read_text(encoding="utf-8"), "", cap)
        other = (parse_policies(args.against.read_text(encoding="utf-8"), "", cap)
                 if args.against else None)

        # The event schema, which decides what the policy MEANS before anything is checked about
        # what it says. Both halves, and they are different jobs: a partial pin becomes an
        # ordinary conjunct, a universal one a partition key stamped onto every term.
        schema = ({"keys": [], "partial": {}, "max_window": DEFAULT_MAX_WINDOW}
                  if args.event_schema is None
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
        reading = (f"under {args.event_schema.name}: partitioned by "
                   f"{', '.join(schema['keys'])} -- a temporal predicate sees only its own partition")
    elif args.event_schema is not None:
        reading = f"under {args.event_schema.name}: no universal pin, so global-trace semantics"
    else:
        reading = ("no --event-schema given, so every answer below assumes the UNPINNED reading\n"
                   "  (global trace). The shipped DEFAULT partitions by principal, under which a rule\n"
                   "  reported live here may never fire.")

    # Before the preamble is printed, because the description is JSON and a prose line above it
    # would make the whole document unparseable.
    if args.describe:
        return describe(args, policies, vocab, schema, reading)

    print(reading + "\n")

    if args.property_module is not None:
        return prove(args, policies, vocab, schema["keys"])

    if args.against is not None:
        return diff(args, policies, other, vocab, schema["keys"])

    permits = [i + 1 for i, p in enumerate(policies) if p["effect"] == "permit"]
    forbids = [i + 1 for i, p in enumerate(policies) if p["effect"] == "forbid"]

    tier = (f", SMOKE: {args.smoke} random sessions, not exhaustive"
            if args.smoke else "")
    print(f"{args.policy.name}: {len(permits)} permit(s), {len(forbids)} forbid(s), "
          f"bound {args.attempts} attempts{tier}\n")

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
            matters, out = check_one(work, i, args.attempts, args.amount, "NeverMatters",
                                     smoke=args.smoke)

            # For a permit, ask the sharper question too. Vacuous implies redundant, so a
            # permit reported vacuous is also deletable -- but "never fires at all" is a more
            # useful thing to be told than "something else covers it".
            fires = None
            if rule["effect"] == "permit":
                fires, fout = check_one(work, i, args.attempts, args.amount, "NeverFires",
                                        smoke=args.smoke)
                if fires:
                    out = fout

            # `None` only ever arrives from a smoke run, and only the absence claims are
            # blocked by it: a witness found by a random walk settles `live` for good.
            if matters:
                verdict, note = "live", f"witness: {witness(out)}"
            elif rule["effect"] == "permit" and fires is None:
                verdict, note = "unknown", f"no witness in {args.smoke} random sessions -- not a verdict"
            elif rule["effect"] == "permit" and not fires:
                verdict, note = "VACUOUS", f"no session of up to {args.attempts} attempts makes it grant"
            elif matters is None:
                verdict, note = "unknown", f"no witness in {args.smoke} random sessions -- not a verdict"
            elif not matters:
                verdict = "REDUNDANT" if rule["effect"] == "permit" else "DEAD"
                note = "deleting it changes no verdict in any session"

            findings.append((i, rule["effect"], verdict))
            print(f"  {label:34} {verdict:10}{note}")

            if args.verbose:
                print("\n".join(f"      {line}" for line in out.splitlines()))

    print()

    # `unknown` is NOT a finding, and must not be summarised as one. Advice to delete a rule we
    # merely did not search hard enough for is the one wrong answer that matters here.
    unknown = [(i, e, v) for i, e, v in findings if v == "unknown"]
    if unknown:
        for i, effect, _ in unknown:
            print(f"unknown {effect} #{i}")
        print()
        print(f"A random walk of {args.smoke} sessions found no witness for these. That is NOT a")
        print("finding: it does not mean the rule is inert, only that this search did not reach a")
        print("session where it matters. Re-run without --smoke to get a verdict, or raise --smoke")
        print("to search further.\n")

    dead = [(i, e, v) for i, e, v in findings if v not in ("live", "unknown")]
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
    elif not unknown:
        print(f"every rule is load-bearing within {args.attempts} attempts.\n"
              "That is not a proof of correctness -- only that none of them is inert.")

    # Vacuity is a finding, not an error. The exit code says whether the run ANSWERED.
    return 0


if __name__ == "__main__":
    sys.exit(main())
