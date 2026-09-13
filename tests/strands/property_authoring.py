"""The property-authoring gate, checked without a model.

    python tests/strands/property_authoring.py

THE GATE IS THE FEATURE. Drafting a property module is a convenience; refusing to keep one that
says nothing is what makes the convenience safe. The literature's most-reported pathology in
agentic verification is a model asked to produce both an artifact and its specification
discovering that a trivial specification is the cheapest way to pass -- and the failure mode is a
property that is perfectly, uselessly true.

So the case that matters here is the negative one: a property that HOLDS and catches no mutant
must be REJECTED, and nothing must be written. A green run over a directory of true-and-empty
properties is exactly the false confidence this project exists to prevent.

The checker underneath is REAL. These run TLC.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent.author import assess, author  # noqa: E402

POLICIES = REPO / "tests" / "policies"

# Parses, holds of every policy, and constrains nothing: its variable has no connection to the
# policy at all. The shape a model reaches for when a real claim is hard.
#
# TAKES THE NAME IT WILL BE WRITTEN UNDER, because TLA+ requires the module name to match its file
# name. A fixed name here would make this module fail to PARSE whenever the loop wrote it to a
# differently-named file, and a parse failure is a different rejection from the one being tested --
# the test would pass while never reaching the gate.
def trivial(name: str) -> str:
    return f"""---------------------------- MODULE {name} ----------------------------
EXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest

VARIABLE x
Init == x = 1
Next == UNCHANGED x
Spec == Init /\\ [][Next]_x

AlwaysTrue == x = 1

=============================================================================
"""


TRIVIAL = trivial("Trivial")
TRIVIAL_CFG = "SPECIFICATION Spec\nINVARIANT AlwaysTrue\n"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  -- ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


def scripted(*pairs):
    calls = {"n": 0}
    seen: list[str] = []

    def propose(vocab, intent, feedback):
        seen.append(feedback)
        i = min(calls["n"], len(pairs) - 1)
        calls["n"] += 1
        return pairs[i]

    propose.seen = seen                                 # type: ignore[attr-defined]
    return propose


def main() -> int:
    # --- assess(): the gate's own logic ----------------------------------------------------------
    check("a module that did not run is rejected",
          bool(assess({"ran": False, "output": "boom"}, "INVARIANT X")))
    check("a .cfg naming no invariant is rejected",
          any("no INVARIANT" in c for c in assess({"ran": True, "holds": True, "caught": 3}, "")))
    check("holding while catching NOTHING is rejected",
          any("every broken version" in c
              for c in assess({"ran": True, "holds": True, "caught": 0}, "INVARIANT X")))
    check("holding and catching something is accepted",
          assess({"ran": True, "holds": True, "caught": 1}, "INVARIANT X") == [])
    # A property that FAILS on the real policy has already shown it discriminates -- that is a
    # finding about the policy, not a defect in the property, and must not be rejected.
    check("a property that fails on the real policy is accepted",
          assess({"ran": True, "holds": False, "caught": None}, "INVARIANT X") == [])

    with tempfile.TemporaryDirectory(prefix="anchor-author-test-") as tmp:
        work = Path(tmp)
        shutil.copy(POLICIES / "firewall.dw", work)
        policy = work / "firewall.dw"

        good = (POLICIES / "firewall.tla").read_text(encoding="utf-8")
        good_cfg = (POLICIES / "firewall.cfg").read_text(encoding="utf-8")

        # --- THE ONE THAT MATTERS: true and empty is refused ------------------------------------
        out = work / "out"
        run = author(policy, "anything", scripted((TRIVIAL, TRIVIAL_CFG)),
                     rounds=1, mutants=4, out_dir=out, module_name="Trivial")

        check("a true-but-empty property is rejected", run.accepted is None,
              str(run.drafts[-1].complaints if run.drafts else "no drafts"))
        check("it was rejected for catching nothing",
              any("every broken version" in c for c in run.drafts[0].complaints),
              str(run.drafts[0].complaints))
        check("and NOTHING was written", not (out / "Trivial.tla").exists())

        # --- a real property is kept -------------------------------------------------------------
        # firewall.tla is named `firewall`, so it must be written as firewall.tla to parse.
        kept = author(policy, "local ssh allowed, outside refused",
                      scripted((good, good_cfg)), rounds=1, mutants=6,
                      out_dir=out, module_name="firewall")

        check("a property that holds AND discriminates is accepted", kept.accepted is not None,
              str(kept.drafts[-1].complaints if kept.drafts else "no drafts"))
        check("it caught at least one mutant", (kept.accepted.caught or 0) >= 1,
              str(kept.accepted.caught if kept.accepted else None))
        check("and it was written", (out / "firewall.tla").exists())

        # --- a rejected draft must not clobber a property already on disk ------------------------
        # The realistic disaster: a second attempt overwrites a module somebody wrote by hand, and
        # the failed draft is what is left behind.
        before = (out / "firewall.tla").read_text(encoding="utf-8")
        clobber = author(policy, "anything", scripted((trivial("firewall"), TRIVIAL_CFG)),
                         rounds=1, mutants=4, out_dir=out, module_name="firewall")

        check("a rejected draft is not kept", clobber.accepted is None)
        check("and the existing module is restored, not clobbered",
              (out / "firewall.tla").read_text(encoding="utf-8") == before)

        # --- the objection reaches the next round ------------------------------------------------
        proposer = scripted((trivial("firewall"), TRIVIAL_CFG), (good, good_cfg))
        two = author(policy, "x", proposer, rounds=2, mutants=6,
                     out_dir=out, module_name="firewall")
        check("a second draft is accepted after the first is refused", two.accepted is not None)
        check("and round 2 was told why round 1 failed",
              "every broken version" in proposer.seen[1],        # type: ignore[attr-defined]
              repr(proposer.seen[1][:90]))                        # type: ignore[attr-defined]

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("a drafted property is kept only if it could have failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
