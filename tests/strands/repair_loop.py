"""The repair loop's mechanics, checked without a model.

    python tests/strands/repair_loop.py

WHY THIS NEEDS NO MODEL. `repair()` takes its proposer as an argument, so the loop can be driven
by a scripted one that returns known-bad text and then known-good text. What is being tested is
the LOOP -- does a defect get caught, does the objection reach the next round, does the bound
actually bound, does an accepted candidate stop it -- and none of that depends on a model being
good at anything. The model's judgement is the part that cannot be tested here; the mechanics are
the part where the mistakes live, and they are verifiable on every run rather than on the runs
somebody is willing to pay for.

The checker underneath is REAL. These run TLC.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent.repair import Round, assess, check_property, repair  # noqa: E402

POLICIES = REPO / "tests" / "policies"

# A permit and a forbid that denies nothing, because nothing was going to be allowed anyway.
DEAD = (POLICIES / "dead_forbid.dw").read_text(encoding="utf-8")

# The same file with the dead forbid removed. The repair the checker is asking for.
FIXED = """permit (
    principal,
    action == Anchor::Action::"Trade",
    resource
);
"""

# Neither well-formed nor in the modelled subset: the checker refuses rather than answering, which
# has to reach the next round as a complaint instead of crashing the loop.
GIBBERISH = "permit (principal, action == Anchor::Action::\"Trade\"\n"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def scripted(*answers: str):
    """A proposer that returns its answers in order, recording the feedback it was given."""
    seen: list[str] = []
    calls = {"n": 0}

    def propose(current: str, request: str, feedback: str) -> str:
        seen.append(feedback)
        i = min(calls["n"], len(answers) - 1)
        calls["n"] += 1
        return answers[i]

    propose.feedback_seen = seen        # type: ignore[attr-defined]
    return propose


def main() -> int:
    policy = POLICIES / "dead_forbid.dw"

    # --- the loop catches a defect, complains, and accepts the fix -------------------------------
    proposer = scripted(DEAD, FIXED)
    run = repair(policy, "remove anything that does nothing", proposer, rounds=3)

    check("a dead rule is rejected in round 1",
          len(run.rounds) >= 1 and not run.rounds[0].accepted,
          str(run.rounds[0].complaints if run.rounds else "no rounds"))
    check("the complaint names the DEAD forbid",
          any("DEAD" in c for c in run.rounds[0].complaints),
          str(run.rounds[0].complaints))
    check("the fixed policy is accepted", run.accepted is not None,
          str(run.rounds[-1].complaints))
    check("it stopped as soon as it was accepted", len(run.rounds) == 2, f"{len(run.rounds)} rounds")

    # THE FEEDBACK ACTUALLY REACHED THE MODEL. A loop that checks and then throws the objection
    # away would pass every assertion above -- the second answer is right regardless.
    seen = proposer.feedback_seen                      # type: ignore[attr-defined]
    check("round 1 was given no feedback", seen[0] == "")
    check("round 2 was given the objection", "DEAD" in seen[1], repr(seen[1][:80]))

    # --- the bound bounds -----------------------------------------------------------------------
    stubborn = scripted(DEAD)                          # never fixes it
    capped = repair(policy, "remove anything that does nothing", stubborn, rounds=2)
    check("a proposer that never fixes it runs out", capped.accepted is None)
    check("and runs out AT the bound, not past it", len(capped.rounds) == 2,
          f"{len(capped.rounds)} rounds")
    check("running out is reported as exhausted", capped.exhausted)

    # --- a refusal is data, not a crash ---------------------------------------------------------
    broken = scripted(GIBBERISH, FIXED)
    recovered = repair(policy, "fix it", broken, rounds=2)
    check("an unparseable candidate does not crash the loop", len(recovered.rounds) >= 1)
    check("the refusal becomes a complaint",
          bool(recovered.rounds[0].complaints), str(recovered.rounds[0].complaints))
    check("and the loop carries on to accept a good one", recovered.accepted is not None)

    # --- no_widening is enforced in CODE, not by asking nicely ----------------------------------
    # docs_trading permits approvals; the _forbidden variant does not. Proposing the permissive
    # one against the restrictive baseline is a widening, and must be refused when barred.
    permissive = (POLICIES / "docs_trading.dw").read_text(encoding="utf-8")
    widened = repair(POLICIES / "docs_trading_forbidden.dw", "allow approvals",
                     scripted(permissive), rounds=1, no_widening=True)
    check("a widening candidate is rejected when --no-widening is set",
          widened.accepted is None, str(widened.rounds[0].complaints))
    check("the objection quotes what was newly allowed",
          any("ApproveSale" in c for c in widened.rounds[0].complaints),
          str(widened.rounds[0].complaints))

    # The SAME candidate, with the bar lifted, is fine. Without this the test above would pass on
    # a loop that rejected everything.
    allowed = repair(POLICIES / "docs_trading_forbidden.dw", "allow approvals",
                     scripted(permissive), rounds=1, no_widening=False)
    check("and is accepted when widening is permitted", allowed.accepted is not None,
          str(allowed.rounds[0].complaints))

    # --- assess() does not invent defects out of `unknown` --------------------------------------
    unknown_only = assess({"rules": [{"index": 1, "effect": "permit", "actions": ["X"],
                                      "verdict": "unknown", "note": "no witness"}],
                           "unknown": [1], "defects": []}, None, no_widening=False)
    check("`unknown` is not treated as a defect to fix",
          all("VACUOUS" not in c and "DEAD" not in c for c in unknown_only), str(unknown_only))
    check("but it is still mentioned", bool(unknown_only))

    # --- THE STATED PROPERTY, as an acceptance criterion -----------------------------------------
    # This path had no coverage, and was broken the whole time: the loop asked for `--json` and
    # `--property` together, a property run prints PROSE, the parse failed, and every candidate was
    # rejected with "the checker could not produce a verdict" -- including the ones that satisfied
    # the property. A gate that says no whatever happens is not a gate, and nothing noticed because
    # nothing asked.
    held = check_property(POLICIES / "firewall.dw", POLICIES / "firewall.tla")
    check("a candidate that satisfies the property draws no complaint",
          held.get("held") is True
          and assess({"rules": []}, None, no_widening=False, prop=held) == [],
          str(held.get("_why") or held.get("held")))

    broken = check_property(POLICIES / "firewall_open.dw", POLICIES / "firewall.tla")
    said = assess({"rules": []}, None, no_widening=False, prop=broken)
    check("a candidate that breaks it is rejected",
          broken.get("held") is False and bool(said),
          str(broken.get("_why") or broken.get("held")))
    check("and the complaint NAMES the claim and the state that breaks it",
          bool(said) and "OutsideIsRefused" in said[0] and "external" in said[0],
          str(said[:1]))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("the repair loop's mechanics hold; only the model's judgement is untested here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
