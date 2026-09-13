"""The unattended directory check, without a model.

    python tests/strands/auto_directory.py

WHAT IS WORTH PINNING HERE is not that the checks work -- they have their own tests -- but that the
ORCHESTRATION cannot quietly do less than it claims:

    every policy is found by globbing      a skipped policy in a clean report is worse than none
    a .tla is paired with its own policy    and one that names none is REPORTED, not dropped
    findings are ordered intent-first       a broken intention outranks an inert rule
    a directory with no intentions SAYS SO  its clean report means much less, and nothing else
                                            in the file distinguishes the two

The last is the one that would rot silently. `auto` over a directory of policies with no stated
intentions produces a report that looks exactly like a pass, and the only thing standing between
that and a false sense of security is a paragraph this test insists on.

The checker underneath is REAL. These run TLC.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent.auto import (check_all, discover, findings_of,  # noqa: E402
                        parse_questions, report)

POLICIES = REPO / "tests" / "policies"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    # --- questions parse out of markdown --------------------------------------------------------
    qs = parse_questions("""
### 1. First one
*Policy:* `a.dw`
> Is this doing anything?

### 2. Second one
*Policies:* `new.dw` against `old.dw`
> What changed?
> Show me an example.

### 3. Not a question
Just prose, no blockquote.
""")
    check("questions are found", len(qs) == 2, str([q.heading for q in qs]))
    check("a question's policy is read", qs[0].policy == "a.dw", qs[0].policy)
    check("a comparison names both files",
          (qs[1].policy, qs[1].against) == ("new.dw", "old.dw"), str(qs[1]))
    check("multi-line questions are joined", "Show me an example." in qs[1].text, qs[1].text)
    check("a section with no question is not one", all(q.heading != "3. Not a question" for q in qs))

    with tempfile.TemporaryDirectory(prefix="anchor-auto-test-") as tmp:
        work = Path(tmp)

        # --- a directory with policies and ONE stated intention ---------------------------------
        shutil.copy(POLICIES / "dead_forbid.dw", work)
        shutil.copy(POLICIES / "firewall.dw", work)
        shutil.copy(POLICIES / "firewall.tla", work)
        shutil.copy(POLICIES / "firewall.cfg", work)

        # A module whose header names no policy here: must be REPORTED, never guessed at.
        (work / "Orphan.tla").write_text(
            "---- MODULE Orphan ----\n\\* names no policy\n====\n", encoding="utf-8")
        (work / "Orphan.cfg").write_text("SPECIFICATION Spec\n", encoding="utf-8")

        plan = discover(work)
        check("every .dw is found", len(plan.policies) == 2, str([p.name for p in plan.policies]))
        check("a .tla is paired with the policy its header names",
              [(m.name, p.name) for m, p in plan.properties] == [("firewall.tla", "firewall.dw")],
              str(plan.properties))
        check("a module naming no policy is reported, not dropped",
              len(plan.unpaired) == 1 and plan.unpaired[0][0].name == "Orphan.tla",
              str(plan.unpaired))

        out = work / "out"
        out.mkdir()
        results = check_all(plan, out)
        findings = findings_of(results)

        check("the inert rule is found",
              any("DEAD" in f and "dead_forbid" in f for f in findings), str(findings))
        check("the satisfied intention produces no finding",
              not any("firewall.tla" in f for f in findings), str(findings))
        check("traces are kept per policy", (out / "traces" / "dead_forbid").is_dir())

        text = report(plan, results, findings, model_used=False)
        check("the report names the unpaired module", "Orphan.tla" in text)
        check("a directory WITH intentions gets no missing-intent warning",
              "No stated intentions were found" not in text)

        # --- the honesty case: no stated intentions at all --------------------------------------
        #
        # `docs_trading.dw` and not `firewall.dw`, which would have made this case say the wrong
        # thing: firewall's forbid IS dead -- nothing with `origin == "external"` was ever going to
        # be permitted, so it denies nothing the rest of the set would have allowed. Defensible as
        # defence in depth, and still a finding. What this case needs is a policy with no findings
        # at all, so that the only thing keeping the report honest is the missing-intent paragraph.
        bare = work / "bare"
        bare.mkdir()
        shutil.copy(POLICIES / "docs_trading.dw", bare)
        bare_plan = discover(bare)
        bare_out = bare / "out"
        bare_out.mkdir()
        bare_results = check_all(bare_plan, bare_out)
        bare_findings = findings_of(bare_results)
        bare_text = report(bare_plan, bare_results, bare_findings, model_used=False)

        check("a clean directory produces no findings", bare_findings == [], str(bare_findings))
        check("BUT the report says no intentions were stated",
              "No stated intentions were found" in bare_text, bare_text[:200])
        # The headline must not be a vacuous truth: with zero intentions, "every stated intention
        # holds" is true and says nothing, which is the exact failure this project exists to catch.
        check("and does not claim every intention holds",
              "every stated intention holds" not in bare_text, bare_text[:300])

        # --- ordering: a broken intention outranks an inert rule --------------------------------
        ordered = findings_of({
            "derived": {"x.dw": {"rules": [{"index": 1, "effect": "permit", "verdict": "VACUOUS",
                                            "note": "n", "blame": None}]}},
            "properties": {"P.tla": {"policy": "x.dw", "held": False}},
        })
        check("a broken intention is listed first",
              ordered and "does not satisfy" in ordered[0], str(ordered))

        # A checker that could not answer must not read as a pass.
        broke = findings_of({"derived": {"x.dw": {"_failed": True, "_why": "boom"}},
                             "properties": {}})
        check("a policy that could not be checked is a finding",
              broke and "could not be checked" in broke[0], str(broke))

        json.dumps(results, default=str)          # must be serialisable for results.json
        check("results serialise to JSON", True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("the directory check finds everything it claims to, and says what it did not check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
