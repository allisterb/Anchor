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
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"

sys.path.insert(0, str(REPO / "src"))

from translator import (DECISION_KIND, DEFAULT_MAX_WINDOW, Unsupported, apply_pins,  # noqa: E402
                        find_jar, generate_policy_module, parse_policies, parse_schema, run_tlc,
                        narrate, stamp_keys, vocabulary, witness_events)

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


@contextmanager
def workdir(args, prefix: str):
    """Where a run's generated TLA+ lives -- a temp directory, or `--keep DIR` if one was asked for.

    THE ARTIFACTS ARE THE ARGUMENT. A verdict from a model checker is only as good as the model,
    and until now the model was written into a temp directory and deleted on the way out, so
    nobody could examine the thing the answer came from. That is a bad position for a project
    whose whole claim is that its answers are checkable: "trust me, TLC said so" is the opposite
    of formal methods.

    With `--keep` the directory holds `PolicyUnderTest.tla` (generated from the policy text),
    `Vacuity.tla`, `DogwoodSemantics.tla`, the `.cfg` naming the invariant and the bounds, and the
    raw TLC output per run. That is enough to re-run the check by hand and to disagree with it.
    """
    if args.keep:
        args.keep.mkdir(parents=True, exist_ok=True)
        yield args.keep
        return
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        yield Path(tmp)


def keep_run(args, work: Path, name: str, out: str) -> None:
    """Preserve one TLC run: the config it actually used, and the output it produced.

    THE CONFIG IS COPIED, NOT REBUILT. `check_one` writes `Vacuity.cfg` before each run, so the
    file on disk is the one TLC read -- copying it cannot drift from what ran, whereas formatting
    a second copy from the same template could, and would do it silently. Called immediately after
    each run, because the next one overwrites `Vacuity.cfg`.

    No-op without `--keep`.
    """
    if not args.keep:
        return
    (work / f"{name}.tlc.txt").write_text(out, encoding="utf-8")
    cfg = work / "Vacuity.cfg"
    if cfg.exists():
        shutil.copyfile(cfg, work / f"{name}.cfg")


def keep_readme(args, work: Path, runs: list[tuple[str, str]]) -> None:
    """Explain the kept directory well enough that someone can re-run it and disagree.

    A directory of `.tla` files is not reproducibility on its own. TLC takes its configuration
    from a file named after the MODULE, so a config kept under a run's own name cannot be used
    where it lies -- and a reader would have to work that out from an error message.

    `runs` is (config stem, module stem). They differ for the built-in questions, which all run
    the `Vacuity` module under several configs, and coincide for a property module, which brings
    its own correctly-named config and needs no copying. The commands below reflect which.
    """
    if not args.keep:
        return
    # The REAL jar, not a plausible-looking name. It carries its version -- tla2tools-1.7.4.jar --
    # and a README promising reproducibility with a path that does not exist is worse than one
    # that says nothing.
    try:
        jar = str(find_jar())
    except Exception:                                             # noqa: BLE001
        jar = "lib/tla2tools-<version>.jar   (not found when this was written)"

    against = getattr(args, "against", None)
    lines = [
        "# The model this verdict came from",
        "",
        f"Generated by `src/checker/properties.py` from `{args.policy.name}`"
        + (f" against `{against.name}`" if against else "")
        + ". Everything TLC",
        "was given is here, so the run can be repeated and the answer argued with.",
        "",
        "| file | |",
        "|---|---|",
    ]

    # Only what is actually here. A property run brings its own module and never copies
    # `Vacuity.tla`, so listing it unconditionally would describe a file the reader cannot find --
    # a small lie, in a document whose whole job is to be checkable.
    described = [
        ("PolicyUnderTest.tla", "generated from the policy TEXT -- the actions, event kinds and"
                                " field domains the policy actually reads, plus the rules as records"),
        ("Vacuity.tla", "the session model and the built-in questions asked of it"),
        ("DogwoodSemantics.tla", "the evaluator, shared with the differential tests"),
    ]
    lines += [f"| `{name}` | {what} |" for name, what in described if (work / name).exists()]
    lines += [
        "| `*.cfg` | the configuration each run used, copied as it ran |",
        "| `*.tlc.txt` | the raw TLC output for each run, counterexample included |",
        "",
        "## Re-running",
        "",
    ]

    needs_copy = [(cfg, mod) for cfg, mod in runs if cfg != mod]
    if needs_copy:
        lines += [
            "**TLC reads its config from a file named after the module**, so these have to be"
            " copied into",
            "place first -- they cannot be passed under their own names:",
            "",
        ]
    lines.append("```bash")
    for cfg, mod in runs:
        if cfg == mod:
            lines.append(f"java -cp {jar} tlc2.TLC -config {cfg}.cfg {mod}")
        else:
            lines.append(f"cp {cfg}.cfg {mod}.cfg && java -cp {jar} tlc2.TLC -config {mod}.cfg {mod}")
    lines += [
        "```",
        "",
        "## Reading the result BACKWARDS",
        "",
        "The built-in questions are asked as invariants that are **meant to fail**. TLA+ has no"
        " existential",
        "path quantifier, so reachability is asked by checking the negation: a *violation* is the"
        " witness,",
        "and a clean run is the claim of absence. `properties.py` inverts this before printing,"
        " which is",
        "why the raw output reads the opposite way round.",
        "",
        "| invariant | a violation means |",
        "|---|---|",
        "| `NeverFires` | the target rule CAN grant something -- it is live rather than VACUOUS |",
        "| `NeverMatters` | deleting the target rule WOULD change a verdict -- it is load-bearing |",
        "| `NeverWidened` | the first policy permits a session the second denies -- the edit ADDED"
        " a permission |",
        "| `NeverNarrowed` | the first denies a session the second permits -- it REMOVED one |",
        "",
        "**A property module of your own is the exception**: it is meant to HOLD, and a violation"
        " names the",
        "request that breaks your claim. No inversion there.",
        "",
        "## What the bound was",
        "",
        f"`MaxAttempts = {args.attempts}`, `MaxAmount = {args.amount}`. Every negative answer is"
        " bounded by",
        "those and by nothing else; raising them trades runtime for confidence. `Target` selects"
        " which rule",
        "a run is about -- `0` means the second policy file. Each `.cfg` carries the values that"
        " run used.",
        "",
    ]
    (work / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    with workdir(args, "anchor-prove-") as work:
        (work / "PolicyUnderTest.tla").write_text(
            generate_policy_module(args.policy, policies, vocab, keys=keys), encoding="utf-8")
        shutil.copyfile(SPECS / "DogwoodSemantics.tla", work / "DogwoodSemantics.tla")

        held, out = check_property(work, args.property_module)

        # The property module brings its own correctly-named .cfg, which `check_property` has
        # already copied in, so nothing needs renaming for a re-run.
        if args.keep:
            (work / f"{args.property_module.stem}.tlc.txt").write_text(out, encoding="utf-8")
            keep_readme(args, work,
                        [(args.property_module.stem, args.property_module.stem)])

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


# ---------------------------------------------------------------------------- permissiveness
# The four verdicts, and the vocabulary is deliberately Cedar Analysis's own: `cedar-lean-cli
# analyze compare` returns Equivalent / More Permissive / Less Permissive / Incomparable. Agreeing
# with the neighbouring tool costs nothing and means a reader who knows one knows the other.
#
# What differs is the DOMAIN. Cedar compares a policy as a function of one REQUEST. This compares
# over SESSIONS, because a Dogwood decision can depend on what happened earlier -- and a rate limit
# or an approval window is invisible to any comparison that looks at one request at a time.
VERDICTS = {
    (False, False): ("EQUIVALENT",
                     "no session of up to {attempts} attempts tells them apart"),
    (True,  False): ("MORE PERMISSIVE",
                     "this edit ADDS permissions"),
    (False, True):  ("LESS PERMISSIVE",
                     "this edit REMOVES permissions"),
    (True,  True):  ("INCOMPARABLE",
                     "this edit both adds and removes permissions -- usually a mistake"),
}


def direction(found, out: str) -> dict | None:
    """One direction of a comparison, as structured data. None when nothing was found.

    `witness` is the one-line summary a person reads; `session` is the same counterexample as
    events, which is what an agent needs -- a repair loop has to know the INPUT VALUES that
    reached the bad decision, and "ApproveSale -> SellShares" does not carry them.
    """
    if not found:
        return None
    events = witness_events(out)
    return {
        "witness": witness(out),
        "session": events,
        # The same session as sentences. Carried rather than left for the caller to compose,
        # so that an agent quoting Anchor and a person reading it see the SAME words -- two
        # renderings of one verdict is one more than the number that can be checked.
        "narrative": narrate(events),
    }


def compare(args, policies: list[dict], other: list[dict], vocab: dict,
            keys: list[str] | None = None, reading: str = "") -> int:
    """Is this policy wider than the one it replaces, narrower, both, or neither?

    TWO TLC RUNS, NOT ONE, and the reason is TLC rather than the question: it stops at the first
    violated invariant, so asking both directions at once would answer whichever it reached first
    and silently drop the other. A run per direction also yields a witness per direction, which is
    what the answer is actually made of -- "you now allow this" is useful, "they differ" is not.

    WHICH DIRECTION IS THE DANGEROUS ONE. A permission removed is a support ticket: somebody is
    locked out, they complain, it gets fixed. A permission silently added is an incident. So the
    widening witness is reported first and at greater length, even though the question people ask
    out loud is usually the other one.
    """
    tier = f", SMOKE: {args.smoke} random sessions, not exhaustive" if args.smoke else ""
    if not args.json:
        print(f"{args.policy.name} vs {args.against.name}: "
              f"{len(policies)} rule(s) vs {len(other)}, bound {args.attempts} attempts{tier}\n")

    with workdir(args, "anchor-compare-") as work:
        (work / "PolicyUnderTest.tla").write_text(
            generate_policy_module(args.policy, policies, vocab, other, args.against.name, keys),
            encoding="utf-8")
        for module in ("Vacuity.tla", "DogwoodSemantics.tla"):
            shutil.copyfile(SPECS / module, work / module)

        # Target = 0 selects `Other` -- the second file -- as the set compared against.
        wider, wider_out = check_one(work, 0, args.attempts, args.amount,
                                     "NeverWidened", args.smoke)
        keep_run(args, work, "NeverWidened", wider_out)

        narrower, narrower_out = check_one(work, 0, args.attempts, args.amount,
                                           "NeverNarrowed", args.smoke)
        keep_run(args, work, "NeverNarrowed", narrower_out)

        # The .cfg left on disk is whichever ran LAST, which would misrepresent the first run to
        # anyone re-running by hand. `keep_run` copied each one as it went; this names the modules
        # they belong to.
        keep_readme(args, work, [("NeverWidened", "Vacuity"), ("NeverNarrowed", "Vacuity")])

        if args.verbose and not args.json:
            for label, out in (("NeverWidened", wider_out), ("NeverNarrowed", narrower_out)):
                print(f"    ---- {label} ----")
                print("\n".join(f"    {line}" for line in out.splitlines()))

    # A smoke run answers True or None and NEVER False, because it cannot establish absence. The
    # unknown must not collapse into "no": "this edit adds no permissions" is exactly the sentence
    # somebody would ship on.
    unknown = wider is None or narrower is None
    verdict, gloss = ("UNKNOWN", "a random walk cannot rule a difference out") if unknown \
        else VERDICTS[(wider, narrower)]

    if args.json:
        print(json.dumps({
            "policy": args.policy.name,
            "against": args.against.name,
            # Flattened: the prose form is wrapped for a terminal, and embedded newlines in a
            # JSON string are just noise to whatever is parsing this.
            "reading": " ".join(reading.split()),
            "bound": {"attempts": args.attempts, "amount": args.amount,
                      "exhaustive": not args.smoke,
                      "randomSessions": args.smoke or None},
            "verdict": verdict,
            # Null means "not found", which under --smoke is NOT the same as "does not exist".
            # `bound.exhaustive` is what says which of the two this null is.
            "added": direction(wider, wider_out),
            "removed": direction(narrower, narrower_out),
            "artifacts": str(args.keep) if args.keep else None,
        }, indent=2))
        return 0

    print(f"  {verdict}   {gloss.format(attempts=args.attempts) if not unknown else gloss}\n")

    if unknown:
        found = [what for what, v in (("adds", wider), ("removes", narrower)) if v]
        print(f"  a random walk found {' and '.join(found) or 'no difference'}, which settles "
              f"{'that much' if found else 'nothing'}.\n")
        print("A smoke run can only ever FIND a difference, never rule one out. Re-run without\n"
              "--smoke for a verdict that distinguishes EQUIVALENT from not-yet-found.")
        return 0

    if wider:
        print("  ADDED     a session this policy permits and the old one denies:\n")
        for line in narrate(witness_events(wider_out),
                            f"{args.against.name} DENIES this") or [f"  {witness(wider_out)}"]:
            print(f"              {line}")
        print("\n            This is the direction worth reading twice -- it is what the edit\n"
              "            grants that nobody asked it to grant.")
    if narrower:
        if wider:
            print()
        print("  REMOVED   a session the old policy permitted and this one denies:\n")
        for line in narrate(witness_events(narrower_out),
                            f"{args.policy.name} DENIES this") or [f"  {witness(narrower_out)}"]:
            print(f"              {line}")

    if not wider and not narrower:
        print("Within the bound the two files are interchangeable: every session either set\n"
              "allows, the other allows too. That is a statement about DECISIONS, not about\n"
              "text -- the files may well read very differently.")
    else:
        print("\n--json gives the witness as structured events rather than this summary, and\n"
              "--keep DIR writes the model, the .cfg and the raw TLC output for re-running.")

    if args.keep:
        print(f"\nartifacts: {args.keep}")

    print(f"\nBOUNDED. Sessions of up to {args.attempts} attempts, and the comparison is driven\n"
          "along histories the NEW set produces -- sound because the two agree up to the first\n"
          "point they disagree, which is the point this reports. A difference appearing only in\n"
          "longer sessions is not excluded by this run.")
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
                    help="a second .dw file -- the version being replaced. Reports whether this "
                         "policy is MORE PERMISSIVE, LESS PERMISSIVE, EQUIVALENT or INCOMPARABLE "
                         "to it, with a witness session for each direction, rather than checking "
                         "each rule")
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
    ap.add_argument("--json", action="store_true",
                    help="emit the result as JSON, including the witness SESSION as structured "
                         "events rather than a one-line summary. For an agent, or anything else "
                         "that has to act on the answer instead of read it")
    ap.add_argument("--keep", type=Path, metavar="DIR",
                    help="write the generated TLA+ module, its .cfg and the raw TLC output here "
                         "instead of discarding them. What a reader who knows TLA+ needs in order "
                         "to disagree: the model as checked, and the command to re-run it")
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

    if not args.json:
        print(reading + "\n")

    if args.property_module is not None:
        return prove(args, policies, vocab, schema["keys"])

    if args.against is not None:
        return compare(args, policies, other, vocab, schema["keys"], reading)

    permits = [i + 1 for i, p in enumerate(policies) if p["effect"] == "permit"]
    forbids = [i + 1 for i, p in enumerate(policies) if p["effect"] == "forbid"]

    tier = (f", SMOKE: {args.smoke} random sessions, not exhaustive"
            if args.smoke else "")
    if not args.json:
        print(f"{args.policy.name}: {len(permits)} permit(s), {len(forbids)} forbid(s), "
              f"bound {args.attempts} attempts{tier}\n")

    if not policies:
        print("nothing to check -- the file declares no rules")
        return 0

    findings = []
    detail: list[dict] = []
    runs: list[tuple[str, str]] = []
    with workdir(args, "anchor-vacuity-") as work:
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
            # One config and one output PER RULE, because each run sets a different `Target`.
            # A single kept pair would describe whichever rule happened to be checked last.
            keep_run(args, work, f"rule-{i}-NeverMatters", out)
            runs.append((f"rule-{i}-NeverMatters", "Vacuity"))

            # For a permit, ask the sharper question too. Vacuous implies redundant, so a
            # permit reported vacuous is also deletable -- but "never fires at all" is a more
            # useful thing to be told than "something else covers it".
            fires = None
            if rule["effect"] == "permit":
                fires, fout = check_one(work, i, args.attempts, args.amount, "NeverFires",
                                        smoke=args.smoke)
                keep_run(args, work, f"rule-{i}-NeverFires", fout)
                runs.append((f"rule-{i}-NeverFires", "Vacuity"))
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

            story = narrate(witness_events(out)) if verdict == "live" else []
            detail.append({
                "index": i,
                "effect": rule["effect"],
                "actions": rule["actions"] or ["(any)"],
                "verdict": verdict,
                "note": note,
                # Only a live rule has a witness: the other verdicts are claims of ABSENCE, and
                # there is no session to show for "this never happens".
                "witness": witness(out) if verdict == "live" else None,
                "session": witness_events(out) if verdict == "live" else [],
                "narrative": story,
            })
            findings.append((i, rule["effect"], verdict))

            if args.json:
                continue

            print(f"  {label:34} {verdict:10}{note}")

            # Only for `live`, and only when the session says more than its one-line summary --
            # a policy reading no input fields narrates to the action names already on the line
            # above, and repeating them would be noise per rule rather than detail.
            if verdict == "live" and any("(" in line and "()" not in line for line in story):
                for line in story:
                    print(f"      {line}")

            if args.verbose:
                print("\n".join(f"      {line}" for line in out.splitlines()))

        keep_readme(args, work, runs)

    if args.json:
        print(json.dumps({
            "policy": args.policy.name,
            "reading": " ".join(reading.split()),
            "bound": {"attempts": args.attempts, "amount": args.amount,
                      "exhaustive": not args.smoke,
                      "randomSessions": args.smoke or None},
            "rules": detail,
            # Pre-computed because every consumer wants them and deriving them means knowing
            # which verdicts are claims of absence -- the distinction this project exists to keep.
            "defects": [r["index"] for r in detail
                        if r["verdict"] in ("VACUOUS", "REDUNDANT", "DEAD")],
            "unknown": [r["index"] for r in detail if r["verdict"] == "unknown"],
            "artifacts": str(args.keep) if args.keep else None,
        }, indent=2))
        return 0

    if args.keep:
        print(f"\nartifacts: {args.keep}")

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
