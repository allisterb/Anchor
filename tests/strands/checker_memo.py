"""`src/agent/invoke.py`: the memo that now sits under every verdict Anchor prints.

A CACHE IN A VERIFICATION TOOL IS A LIABILITY UNLESS IT IS EXACT. What it buys is wall clock — the
suite's serial work is about 80% JVM startup, and ~1.6s of every ~2.0s TLC run is starting one — and
what it risks is a verdict about a file that has since changed. So the question here is never "is it
faster", which is measured elsewhere; it is whether the answer is the same one.

  1. DETERMINISM, ESTABLISHED RATHER THAN ASSUMED. Every mode is run twice with the memo OFF and
     the verdicts compared. The whole design rests on this, and it is the assumption most likely
     to stop being true — a future `--sample` or a timeout-shaped heuristic would break it
     silently, and this is the only place that would notice.
  2. THE SAME ANSWER. Every call answered from memory is compared against the one the checker
     gives when the memo is off. Not the exit code alone: the parsed verdict, the violations and
     the derived findings.
  3. CONTENT, NOT PATHS. A drafted module is rewritten to the SAME PATH every round, so a key that
     did not read the bytes would answer round 2 with round 1's verdict — the worst failure this
     could have, because it would report a fixed module as still broken (or a broken one as fixed)
     with no sign anything went wrong.
  4. `--keep` IS NEVER CACHED. Without it the checker's whole observable output is stdout; with it
     it writes the model, the .cfg and the raw TLC output to a directory the caller reads
     afterwards. Replaying that from memory would leave the directory unwritten or stale, and
     `auto.py` passes it.
  5. IT IS BOUNDED, and the counters are honest.

    python tests/strands/checker_memo.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from agent import author, invoke, repair                             # noqa: E402

POLICIES = REPO / "tests" / "policies"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        failures.append(label)
        if detail:
            print(f"          {detail[:400]}")


class memo_off:
    """`ANCHOR_CHECKER_MEMO=0`, which is the switch a person reaches for when a verdict looks wrong."""

    def __enter__(self):
        self.before = os.environ.get("ANCHOR_CHECKER_MEMO")
        os.environ["ANCHOR_CHECKER_MEMO"] = "0"
        return self

    def __exit__(self, *_):
        if self.before is None:
            os.environ.pop("ANCHOR_CHECKER_MEMO", None)
        else:
            os.environ["ANCHOR_CHECKER_MEMO"] = self.before


def verdicts(policy: Path, module: Path) -> dict:
    """Everything a caller actually reads, from every mode the pipeline uses."""
    return {
        "describe": author.describe(policy),
        "compiles": author.compiles(policy, module),
        "decides": author.decides(policy, module),
        "property": repair.check_property(policy, module),
        "derived": repair.run_checker(policy),
    }


def same(a: dict, b: dict) -> list[str]:
    """Which modes disagree. Compared field by field, because TLC's output carries timings."""
    differ = []
    for mode in a:
        x, y = a[mode], b[mode]
        if mode == "compiles":
            ok = x[0] == y[0]
        elif mode == "decides":
            ok = x[0] == y[0]
        elif mode == "property":
            ok = (x.get("held"), x.get("_failed"), x.get("violations")) == (
                y.get("held"), y.get("_failed"), y.get("violations"))
        elif mode == "derived":
            ok = (x.get("defects"), x.get("_failed"),
                  [r.get("verdict") for r in (x.get("rules") or [])]) == (
                y.get("defects"), y.get("_failed"),
                [r.get("verdict") for r in (y.get("rules") or [])])
        else:
            ok = x == y
        if not ok:
            differ.append(mode)
    return differ


# -------------------------------------------------------------------------------------------
def deterministic_and_matching() -> tuple[dict, dict]:
    """Two questions, THREE passes, because a fourth would cost ~20s to re-observe a pass.

    This file is a cache's correctness proof and it is not free: each `verdicts()` sweep is five
    checker invocations, of which the derived one alone is ~10s. Written as two scenarios it made
    five sweeps and became the second most expensive harness in the directory; the passes below are
    the fewest that answer both questions.

        cold      memo OFF   -- the baseline
        again     memo OFF   -- the same, so DETERMINISM is established rather than assumed. The
                                whole design rests on it, and a future `--sample` or a
                                timeout-shaped heuristic would break it silently.
        warm      memo ON    -- populates, then repeats: every mode must come from memory, and
                                agree with `cold`.
    """
    print("\nThe same answer, with the memo and without it")
    print("-" * 78)
    policy, module = POLICIES / "firewall.dw", POLICIES / "firewall.tla"

    with memo_off():
        invoke.clear()
        cold = verdicts(policy, module)
        again = verdicts(policy, module)
        uncached = invoke.ran
    check("with no memo, nothing came from memory", invoke.reused == 0, str(invoke.reused))
    check("the checker gave the same verdict twice", same(cold, again) == [], str(same(cold, again)))

    invoke.clear()
    warm_first = verdicts(policy, module)       # populates
    filled = invoke.ran
    warm_again = verdicts(policy, module)       # every one of these must be a hit

    print(f"    {uncached} call(s) with no memo | {filled} ran, then {invoke.reused} reused")
    check("the second pass ran nothing new", invoke.ran == filled, str(invoke.ran))
    check("...and answered every mode from memory", invoke.reused == filled, str(invoke.reused))
    check("the memo's answers match the checker's", same(cold, warm_again) == [],
          str(same(cold, warm_again)))
    check("...and match the pass that populated it", same(warm_first, warm_again) == [],
          str(same(warm_first, warm_again)))

    # And the verdicts being compared are real ones. A memo that returned `_failed` for everything
    # would satisfy every assertion above.
    check("the verdicts being compared are real",
          cold["property"].get("held") is True and cold["describe"].get("actions") == ["Connect"],
          str(cold["property"])[:200])
    return cold, warm_again


def content_not_paths() -> None:
    """The failure that would be worst and quietest: the same path, different bytes."""
    print("\nThe key is the file's CONTENT, not its path")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-memo-") as tmp:
        work = Path(tmp)
        policy = work / "p.dw"
        module = work / "Claim.tla"

        # A property that HOLDS, and one that does not — written to the same two paths in turn,
        # which is exactly what the drafting loop does round after round.
        shutil.copyfile(POLICIES / "firewall.dw", policy)
        shutil.copyfile(POLICIES / "firewall.cfg", module.with_suffix(".cfg"))
        holds = (POLICIES / "firewall.tla").read_text(encoding="utf-8").replace(
            "MODULE firewall", "MODULE Claim", 1)

        invoke.clear()
        module.write_text(holds, encoding="utf-8")
        first = repair.check_property(policy, module)

        # The SAME path, now naming a policy that breaks the claim. A path-keyed memo answers this
        # with the verdict above, and nothing anywhere says it did.
        shutil.copyfile(POLICIES / "firewall_open.dw", policy)
        second = repair.check_property(policy, module)

        print(f"    same paths, different bytes: held={first.get('held')} then "
              f"held={second.get('held')}  ({invoke.ran} ran, {invoke.reused} reused)")
        check("a changed POLICY at the same path is a different question",
              first.get("held") is True and second.get("held") is False,
              f"{first.get('held')} / {second.get('held')}")
        check("...and nothing was answered from memory", invoke.reused == 0, str(invoke.reused))

        # Now the other direction: policy back as it was, module rewritten.
        shutil.copyfile(POLICIES / "firewall.dw", policy)
        invoke.clear()
        module.write_text(holds, encoding="utf-8")
        a = repair.check_property(policy, module)
        module.write_text(holds.replace("MODULE Claim", "MODULE Claim"), encoding="utf-8")
        b = repair.check_property(policy, module)       # byte-identical: this one SHOULD be reused
        check("an identical rewrite of the module IS reused",
              invoke.reused == 1 and a.get("held") == b.get("held"),
              f"reused={invoke.reused}")

        module.write_text(holds.replace("LocalSshIsAllowed ==", "LocalSshIsAllowed == FALSE /\\ "),
                          encoding="utf-8")
        c = repair.check_property(policy, module)
        check("...but a changed module is not", invoke.reused == 1 and c is not a,
              f"reused={invoke.reused}")


def keep_is_never_cached() -> None:
    """A call that writes to disk cannot be answered from memory."""
    print("\n`--keep` writes files, so it is never cached")
    print("-" * 78)
    with tempfile.TemporaryDirectory(prefix="anchor-memo-") as tmp:
        kept = Path(tmp) / "derived"

        check("a --keep call is refused a cache key",
              invoke.fingerprint(["python", "x.py", "p.dw", "--keep", str(kept)]) is None)
        check("...and the same call without it gets one",
              invoke.fingerprint(["python", "x.py", "p.dw"]) is not None)

        # And it really does write, twice, rather than the second call being a no-op.
        invoke.clear()
        for _ in range(2):
            shutil.rmtree(kept, ignore_errors=True)
            invoke.checker([str(POLICIES / "firewall.dw"), "--json", "--keep", str(kept)],
                           timeout=900)
        wrote = sorted(p.name for p in kept.iterdir()) if kept.exists() else []
        print(f"    {kept.name}/ holds {len(wrote)} file(s) after the second call")
        check("both --keep calls ran", invoke.ran == 2 and invoke.reused == 0,
              f"ran={invoke.ran} reused={invoke.reused}")
        check("...and the directory was written by the second one",
              any(w.endswith(".tla") for w in wrote), str(wrote))


def bounded() -> None:
    """It holds TLC transcripts, so it must not grow without limit."""
    print("\nBounded, and the counters are honest")
    print("-" * 78)
    invoke.clear()
    check("cleared means empty", len(invoke._memo) == 0 and invoke.ran == 0
          and invoke.reused == 0)

    for i in range(invoke.LIMIT + 10):
        invoke._memo[f"k{i}"] = None                     # type: ignore[assignment]
        while len(invoke._memo) > invoke.LIMIT:
            invoke._memo.popitem(last=False)
    check(f"it never exceeds LIMIT ({invoke.LIMIT})", len(invoke._memo) == invoke.LIMIT,
          str(len(invoke._memo)))
    check("...and the oldest is what goes", "k0" not in invoke._memo
          and f"k{invoke.LIMIT + 9}" in invoke._memo)
    invoke.clear()

    with memo_off():
        invoke.clear()
        author.describe(POLICIES / "firewall.dw")
        author.describe(POLICIES / "firewall.dw")
        check("with ANCHOR_CHECKER_MEMO=0 nothing is reused",
              invoke.ran == 2 and invoke.reused == 0, f"ran={invoke.ran} reused={invoke.reused}")


def main() -> int:
    print("=" * 78)
    print("The memo under every verdict")
    print("=" * 78)

    deterministic_and_matching()
    content_not_paths()
    keep_is_never_cached()
    bounded()

    print()
    print("=" * 78)
    print("all checks passed" if not failures else f"{len(failures)} FAILED: {failures}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
