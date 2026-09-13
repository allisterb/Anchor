"""Ambiguity reporting, checked without a model.

    python tests/strands/clarify_readings.py

WHAT IS ACTUALLY BEING TESTED. Whether a model notices an ambiguity is its own judgement and is not
checkable here. What IS checkable -- and is the whole reason this feature is more than a prompt --
is that a proposed distinction gets VERIFIED before anybody is asked about it:

    two readings that decide some session differently  ->  raised, with the session
    two readings that decide every session alike       ->  NOT raised, however different they look

The second case is the one that keeps the feature honest. An assistant that asks a clarifying
question every time trains people to click past it, and a model can always manufacture a
distinction. Whether one exists is a question with an answer.

The checker underneath is REAL. These run TLC.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent.clarify import Reading, clarify, distinguish, report  # noqa: E402

POLICIES = REPO / "tests" / "policies"

PERMISSIVE = (POLICIES / "docs_trading.dw").read_text(encoding="utf-8")
RESTRICTIVE = (POLICIES / "docs_trading_forbidden.dw").read_text(encoding="utf-8")

# Same decisions, different text: the redundant permit and the file with it deleted. A reading
# pair like this is a distinction in wording only, and must not reach a person.
REDUNDANT = (POLICIES / "redundant_permit.dw").read_text(encoding="utf-8")
MINIMAL = (POLICIES / "redundant_permit_minimal.dw").read_text(encoding="utf-8")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def readings(*pairs: tuple[str, str]) -> list[Reading]:
    return [Reading(label="abcdefgh"[i], gloss=g, candidate=t) for i, (g, t) in enumerate(pairs)]


def main() -> int:
    # --- a real difference is raised, with the session that shows it ----------------------------
    real = distinguish(readings(("approvals are forbidden", RESTRICTIVE),
                                ("approvals are permitted", PERMISSIVE)),
                       name="trading.dw")

    check("a genuine difference is material", real.material, str(real.distinctions))
    check("the differing reading is named", real.distinctions[0].reading.label == "b"
          if real.distinctions else False)
    check("and it comes with a session, not just a verdict",
          bool(real.distinctions and real.distinctions[0].narrative
               and "ApproveSale" in " ".join(real.distinctions[0].narrative)),
          str(real.distinctions[0].narrative if real.distinctions else "none"))

    text = report(real, "should approvals be allowed?")
    check("the report gives both readings and asks",
          "(a)" in text and "(b)" in text and "Which did you mean?" in text, text[:120])

    # --- A DISTINCTION THAT IS NOT ONE IS NOT RAISED ---------------------------------------------
    # These two files read very differently -- one has a rule the other does not -- and decide
    # every session alike. That is exactly the case a model would offer as an ambiguity and a
    # person should never be asked about.
    same = distinguish(readings(("keep the redundant permit", REDUNDANT),
                                ("drop the redundant permit", MINIMAL)),
                       name="redundant.dw")

    check("readings that agree on every session are NOT material", not same.material,
          str(same.distinctions))
    check("and the report says so rather than staying silent",
          "does not matter which you meant" in report(same, "tidy this up"),
          report(same, "tidy this up")[:120])

    # --- one reading is not an ambiguity ----------------------------------------------------------
    single = distinguish(readings(("the only sensible reading", PERMISSIVE)), name="one.dw")
    check("a single reading is never material", not single.material)
    check("and produces no question at all", report(single, "x") == "")

    # --- a reading the checker cannot answer about is recorded, not dropped -----------------------
    broken = distinguish(readings(("fine", RESTRICTIVE),
                                  ("nonsense", 'permit (principal, action ==\n')),
                         name="broken.dw")
    check("an uncheckable reading is recorded as unusable", len(broken.unusable) == 1,
          str(broken.unusable))
    check("it does not masquerade as agreement", not broken.material or bool(broken.distinctions))

    # THE DISTINCTION THAT MATTERS: "I could not tell" must not read as "they are the same".
    both = distinguish(readings(("keep", REDUNDANT), ("drop", MINIMAL),
                                ("nonsense", 'permit (principal, action ==\n')),
                       name="mixed.dw")
    said = report(both, "tidy this up")
    check("an unusable reading is excluded from a no-difference claim",
          "does not cover it" in said, said[:200])

    # --- clarify() passes the proposer's readings through in order --------------------------------
    got = clarify(POLICIES / "docs_trading.dw", "whatever",
                  lambda cur, req, n: [("forbidden", RESTRICTIVE), ("permitted", PERMISSIVE)])
    check("clarify() labels readings a, b in order",
          [r.label for r in got.readings] == ["a", "b"], str([r.label for r in got.readings]))
    check("and finds the difference end to end", got.material)

    # A proposer that returns nothing -- a malformed model reply -- must not look like agreement.
    none = clarify(POLICIES / "docs_trading.dw", "whatever", lambda cur, req, n: [])
    check("no readings is not the same as no ambiguity",
          not none.material and none.readings == [] and report(none, "x") == "")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("ambiguity is verified before it is raised; only the model's noticing is untested here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
