"""Model-check an arbitrary Dogwood policy file for vacuity, one permit at a time.

    python tests/strands/vacuity.py tests/policies/approval_gate_response.dw

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"

sys.path.insert(0, str(REPO / "src"))

from translator import (Unsupported, like_matches, parse_policies, pattern_witnesses,  # noqa: E402
                        policy_seq, run_tlc)

# Event kinds AgentCore records. `request` is the decision event -- the point authorization runs --
# and the outcome is `response` when the action completed, `error` when it was denied.
KINDS = ["request", "response", "error"]
DECISION_KIND = "request"


# ---------------------------------------------------------------------------- vocabulary
def walk(node, seen: dict) -> None:
    """Collect the vocabulary a policy actually reads, so nothing unused is modelled.

    Field LITERALS are collected too. A field's domain is the values the policy compares it
    against plus one it does not, so both matching and not-matching stay reachable -- which is
    what lets fields move independently instead of sharing one domain.
    """
    if not isinstance(node, dict):
        return

    if pred := node.get("pred"):
        if pred.get("action"):
            seen["actions"].add(pred["action"])
        if pred.get("kind"):
            seen["kinds"].add(pred["kind"])
        for b in pred.get("binds", []):
            side = "input" if b["side"] == "input" else "output"
            if b["side"] not in ("input", "output"):
                continue
            seen[side].add(b["field"])
            if b["kind"] == "lit":
                seen["literals"].setdefault((side, b["field"]), set()).add(b["value"])

    if node.get("op") == "cmp":
        seen["input"].add(node["field"])
        seen["literals"].setdefault(("input", node["field"]), set()).add(node["value"])

    if node.get("op") == "like":
        # A pattern names no literal, so it must contribute the values that make it decidable:
        # one the pattern matches, and one it does not. See this module's `like` note.
        seen["input"].add(node["field"])
        hit, miss = pattern_witnesses(node["pattern"])
        lits = seen["literals"].setdefault(("input", node["field"]), set())
        lits.add(hit)
        if miss is not None:
            lits.add(miss)
        # Recorded so `vocabulary` can refuse a field carrying two of them; see the note there.
        seen["patterns"].setdefault(("input", node["field"]), set()).add(
            tuple(node["pattern"]))

    if node.get("op") == "cmp2":
        # Both sides are request fields. Neither names a literal, so both take the default
        # numeric range -- which needs at least two values for the comparison to go either way.
        seen["input"].add(node["field"])
        seen["input"].add(node["other"])

    for key in ("term", "atom", "left", "cond", "agg"):
        walk(node.get(key), seen)
    for child in node.get("args", []) or []:
        walk(child, seen)


def vocabulary(policies: list[dict], amounts: int = 2, max_fields: int = 4) -> dict:
    seen = {"actions": set(), "kinds": set(), "input": set(), "output": set(),
            "literals": {}, "patterns": {}}
    for p in policies:
        seen["actions"].add(p["action"])
        walk(p["cond"], seen)

    # Two `like` patterns on ONE field need a value satisfying BOTH, or the conjunction looks
    # unsatisfiable and the permit is reported VACUOUS though it is live -- `stock like "A*" &&
    # stock like "*L"` is satisfied by "AAPL", while the per-pattern witnesses "A" and "L"
    # satisfy one pattern each. A false VACUOUS tells someone to delete a working rule.
    #
    # Since TLC evaluates the real pattern, adding a candidate can never make something falsely
    # live; it can only fail to be found. So look for one, and refuse only if the search fails,
    # where "no such string exists" and "we did not look hard enough" are indistinguishable.
    for (side, field), pats in seen["patterns"].items():
        if len(pats) < 2:
            continue
        joint = joint_witness(pats)
        if joint is None:
            raise Unsupported(
                f"{side}.{field} is constrained by {len(pats)} `like` patterns at once and no "
                f"value satisfying all of them could be constructed; deciding that needs glob "
                f"intersection, which is not modelled")
        seen["literals"].setdefault((side, field), set()).add(joint)

    # Each field gets its own domain, so fields move independently. The bound is on state space,
    # not on soundness: the request space is the product of the domains, so it grows as
    # values^fields. Refused above the bound rather than run until it is hopeless.
    fields = len(seen["input"]) + len(seen["output"])
    if fields > max_fields:
        raise Unsupported(
            f"policy reads {fields} input/output fields; the request space is the product of "
            f"their domains, so this would explode (limit {max_fields}, raise with --max-fields)")

    unknown = seen["kinds"] - set(KINDS)
    if unknown:
        raise Unsupported(f"event kinds outside AgentCore's convention: {', '.join(sorted(unknown))}")

    seen["domains"] = {key: field_domain(lits, amounts)
                       for key, lits in _all_fields(seen)}
    return seen


def _all_fields(seen: dict):
    for side in ("input", "output"):
        for field in sorted(seen[side]):
            yield (side, field), seen["literals"].get((side, field), set())


def joint_witness(patterns) -> str | None:
    """A string every one of `patterns` matches, or None if none was constructed.

    The candidates are what each pattern literally requires -- its non-wildcard characters, in
    order -- tried alone and concatenated in both orders. That is enough for the shapes a prefix
    or suffix test produces (`A*` with `*L` gives "AL"), and deliberately not a decision
    procedure: the caller treats None as "refuse", never as "unsatisfiable".
    """
    pats = sorted(patterns, key=len)
    parts = ["".join(e for e in pat if e is not None) for pat in pats]

    candidates = list(parts)
    for i, a in enumerate(parts):
        for j, b in enumerate(parts):
            if i != j:
                candidates.append(a + b)
    candidates.append("".join(parts))

    for cand in candidates:
        if all(like_matches(list(pat), cand) for pat in pats):
            return cand
    return None


def field_domain(literals: set, amounts: int) -> list:
    """The values one field may take: every literal the policy names, plus one it does not.

    The extra value is what makes "this field does not match" reachable. Without it a field
    compared only against `true` would always be true, and a policy that depends on it being
    false would be reported vacuous when it is not.

    A field with no literals -- bound only by `_` or by a join with the request's own context --
    gets a small numeric range, which needs at least two values for a join to mean anything.
    """
    if not literals:
        return [("n", x) for x in range(1, max(2, amounts) + 1)]

    kinds = {type(v) is bool and "b" or (type(v) is int and "n" or "s") for v in literals}
    if len(kinds) > 1:
        raise Unsupported(f"field compared against mixed value kinds: {sorted(kinds)}")
    kind = kinds.pop()

    values = [(kind, v) for v in sorted(literals, key=str)]
    if kind == "b":
        # A boolean has only the two, and both are already reachable.
        return [("b", False), ("b", True)]
    values.append(("n", max(v for v in literals) + 1) if kind == "n" else ("s", "\u0000none"))
    return values


def tla_set(names) -> str:
    return "{" + ", ".join(f'"{n}"' for n in sorted(names)) + "}"


def tla_val(kind: str, value) -> str:
    """One tagged scalar. Kind travels with the value so TLC never compares across kinds."""
    if kind == "b":
        return f'[k |-> "b", v |-> {"TRUE" if value else "FALSE"}]'
    if kind == "n":
        return f'[k |-> "n", v |-> {value}]'
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'[k |-> "s", v |-> "{escaped}"]'


def tla_domains(vocab: dict, side: str) -> str:
    """`[field |-> {values}, ...]` -- what each field of one side may take."""
    fields = sorted(vocab[side])
    if not fields:
        # An empty record. `[f \in {} |-> ...]` is the only way to write one in TLA+.
        return '[f \\in {} |-> {}]'
    entries = ", ".join(
        f"{f} |-> {{" + ", ".join(tla_val(k, v) for k, v in vocab["domains"][(side, f)]) + "}"
        for f in fields)
    return f"[{entries}]"


def tla_all_values(vocab: dict) -> str:
    seen, out = set(), []
    for key in sorted(vocab["domains"]):
        for k, v in vocab["domains"][key]:
            if (k, v) not in seen:
                seen.add((k, v))
                out.append(tla_val(k, v))
    return "{" + ", ".join(out) + "}" if out else "{}"


def generate(source: Path, policies: list[dict], vocab: dict,
             other: list[dict] | None = None, other_name: str = "") -> str:
    body = policy_seq(policies)
    # `Other` is the set compared against when Target = 0. With no second file it is `Policies`,
    # which the spec never reads in that case -- Target is then a rule index.
    other_body = policy_seq(other) if other is not None else None

    other_decl = (f"\\* The second set, from {other_name}. Compared against Policies at every\n"
                  f"\\* decision, so a divergence is a session where the edit changed behaviour.\n"
                  f"Other ==\n  <<\n{other_body}\n  >>\n"
                  if other_body is not None else "Other == Policies\n")

    return f"""\\* GENERATED by tests/strands/vacuity.py from {source.name} -- do not edit.
\\*
\\* Translated by the parser that agrees with the Dogwood reference implementation on 786 recorded
\\* corpus pairs. Vacuity.tla checks THESE records, so what is model-checked is the policy as
\\* written rather than as paraphrased.
---------------------------- MODULE PolicyUnderTest ----------------------------
EXTENDS Integers, Sequences

Source == "{source.name}"

\\* The vocabulary is lifted from the policy text: only actions, event kinds and input/output
\\* fields some condition actually reads are modelled. A policy that joins on nothing costs nothing.
Actions      == {tla_set(vocab["actions"])}
Kinds        == {tla_set(vocab["kinds"] | {DECISION_KIND})}
InputFields  == {tla_set(vocab["input"])}
OutputFields == {tla_set(vocab["output"])}
DecisionKind == "{DECISION_KIND}"

\\* Each field's own domain: every literal the policy compares it against, plus one it does not,
\\* so that both matching and not-matching are reachable. Fields move independently, which is
\\* what lets a policy reading several of them be explored at all.
InputDomain  == {tla_domains(vocab, "input")}
OutputDomain == {tla_domains(vocab, "output")}
AllValues    == {tla_all_values(vocab)}

Policies ==
  <<
{body}
  >>

{other_decl}
=============================================================================
"""


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


# ---------------------------------------------------------------------------- diff
def diff(args, policies: list[dict], other: list[dict], vocab: dict) -> int:
    """Is there a session the two files decide differently?

    Target = 0 selects `Other` as the set compared against, so this is one TLC run rather than
    one per rule. A violation of `NeverMatters` is the witness session.
    """
    print(f"{args.policy.name} vs {args.against.name}: "
          f"{len(policies)} rule(s) vs {len(other)}, bound {args.attempts} attempts\n")

    with tempfile.TemporaryDirectory(prefix="anchor-diff-") as tmp:
        work = Path(tmp)
        (work / "PolicyUnderTest.tla").write_text(
            generate(args.policy, policies, vocab, other, args.against.name), encoding="utf-8")
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
    ap.add_argument("--verbose", action="store_true", help="print the TLC output for each permit")
    args = ap.parse_args()

    for f in (args.policy, args.against):
        if f is not None and not f.exists():
            print(f"no such policy file: {f}", file=sys.stderr)
            return 2

    try:
        policies = parse_policies(args.policy.read_text(encoding="utf-8"))
        other = parse_policies(args.against.read_text(encoding="utf-8")) if args.against else None
        # The vocabulary must span BOTH files. A version that adds a permit for an action the
        # other never mentions would otherwise never have that action attempted, and the run
        # would report "no difference" having not looked -- the one wrong answer that matters.
        vocab = vocabulary(policies + (other or []), args.amount, args.max_fields)
    except Unsupported as e:
        # The house rule: refuse rather than approximate. A translator that quietly mishandles a
        # construct produces a verdict nobody can attribute.
        print(f"REFUSED: {args.policy.name} is outside the modelled subset\n  {e}", file=sys.stderr)
        return 2

    if args.against is not None:
        return diff(args, policies, other, vocab)

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
            generate(args.policy, policies, vocab), encoding="utf-8")
        for module in ("Vacuity.tla", "DogwoodSemantics.tla"):
            shutil.copyfile(SPECS / module, work / module)

        for i, rule in enumerate(policies, 1):
            label = f'{rule["effect"]} #{i}  action == {rule["action"]}'

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
