"""Our semantics against Dogwood's own *documentation examples* -- whole policies, not constructs.

`dogwood_differential.py` runs the regression corpus: 521 cases, each isolating one construct, each
recording `true`/`false` per decision. This runs the other corpus, under `dogwood-docs/examples/`,
and it is a different kind of evidence:

    unit corpus      one construct per case, written to test the engine
    examples corpus  whole policies, written to show someone how to use the language

The second is closer to the population that matters for "point the checker at a policy your pipeline
generated", so the number it gives is the more honest answer to "would this work on mine".

TWO DIFFERENCES THAT BITE, both of which silently produce wrong answers if missed:

  * The oracle is the CLI's replay output -- `ALLOW`/`DENY` with the matching rule ids -- not the
    `true`/`false` of the unit fixtures.
  * "time point N" here counts DECISIONS (0,1,2,3). In the unit corpus it indexes the whole trace
    (0,2,4,6). Keying on it would misalign every verdict, so this keys on the `@N` timestamp, which
    means the same thing in both.

    python tests/strands/dogwood_examples.py
    python tests/strands/dogwood_examples.py --verbose    # per-case results

Needs the venv and the submodule; no network and no credentials -- the expected outputs are
recorded, so nothing is executed.
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "ext" / "dogwood" / "dogwood-docs" / "examples"

from dogwood_differential import (case_record, check, generate_module,  # noqa: E402
                                  parse_trace)
from dogwood_parse import Unsupported, parse_policies  # noqa: E402
from dogwood_schema import apply_pins, parse_schema  # noqa: E402

# `@100 (time point 1): ALLOW  [rules: 0, 2]` -- rules appear only on an ALLOW.
VERDICT = re.compile(r"@(\d+) \(time point \d+\):\s*(ALLOW|DENY)(?:\s*\[rules:\s*([\d,\s]*)\])?")


def parse_expected(text: str) -> dict[int, tuple[bool, list[int]]]:
    """`{timestamp: (allowed, rule ids)}`.

    Keyed on the timestamp, NOT the time point: the CLI numbers time points over decisions while
    the unit fixtures index the whole trace, and mixing the two misaligns every verdict.
    """
    out = {}
    for m in VERDICT.finditer(text):
        rules = [int(r) for r in (m.group(3) or "").split(",") if r.strip()]
        out[int(m.group(1))] = (m.group(2) == "ALLOW", rules)
    if not out:
        raise Unsupported("no expected verdicts parsed")
    return out


def oracle_by_index(trace: list[dict],
                    expected: dict[int, tuple[bool, list[int]]]) -> tuple[dict, dict]:
    """Re-key the oracle onto trace positions, which is what the spec indexes by.

    Returns the verdicts and the DETERMINING rule sets separately. Dogwood numbers rules from 0
    over the `permit`/`forbid` declarations in file order -- `def` macros do not consume an id --
    and the spec's policy sequence is 1-based, so every id shifts by one.
    """
    oracle, rules = {}, {}
    for i, e in enumerate(trace, 1):
        if e["time"] in expected and e["decision"]:
            allowed, ids = expected[e["time"]]
            oracle[i] = allowed
            rules[i] = {r + 1 for r in ids}
    if len(oracle) != len(expected):
        raise Unsupported(
            f"{len(expected)} expected verdicts but {len(oracle)} decision events matched them")
    return oracle, rules


def load(case: Path) -> tuple[list[dict], list[dict], dict]:
    """The policies, trace and oracle for one example, or Unsupported with the reason."""
    schema_file = case / "events.dwschema"
    schema = (parse_schema(schema_file.read_text(encoding="utf-8"))
              if schema_file.exists() else {"keys": [], "partial": {}})

    # A `macros.dw` sits beside the policy and its definitions are in scope for it. Inline
    # `def`s in policy.dw itself need no special handling -- one mechanism, two spellings.
    macros = case / "macros.dw"
    policies = parse_policies((case / "policy.dw").read_text(encoding="utf-8"),
                              macros.read_text(encoding="utf-8") if macros.exists() else "")
    apply_pins(policies, schema)

    trace = parse_trace((case / "trace.log").read_text(encoding="utf-8"), schema.get("paths"))
    expected = parse_expected((case / "expected.out").read_text(encoding="utf-8"))
    return (policies, trace) + oracle_by_index(trace, expected)


def unforced(policies: list[dict], oracle: dict[int, bool]) -> int:
    """Decisions whose DETERMINING set the verdict alone does not already pin down.

    With a single permit and no forbid, ALLOW can only mean that permit and DENY can only mean
    nothing matched -- the attribution is then arithmetic, not evidence. It carries information
    when an ALLOW has several permits to choose between, or when a DENY could be either a forbid
    firing or nothing matching at all.
    """
    permits = sum(1 for p in policies if p["effect"] == "permit")
    forbids = len(policies) - permits
    return sum(1 for allowed in oracle.values()
               if (permits > 1 if allowed else forbids > 0))


def main() -> int:
    verbose = "--verbose" in sys.argv

    cases = sorted(d for d in EXAMPLES.iterdir() if d.is_dir())
    runnable = [d for d in cases
                if (d / "trace.log").exists() and (d / "expected.out").exists()]

    records, accepted, refused = [], [], collections.Counter()
    decisions = informative = 0
    for case in runnable:
        try:
            policies, trace, oracle, rules = load(case)
        except Unsupported as e:
            refused[re.sub(r"'[^']*'", "...", e.kind)[:56]] += 1
            if verbose:
                print(f"  REFUSED  {case.name:44} {e}")
            continue
        records.append(case_record(case.name, policies, trace, oracle, rules))
        accepted.append(case.name)
        decisions += len(oracle)
        informative += unforced(policies, oracle)

    print(f"{len(cases)} examples, {len(runnable)} with a trace and expected output\n")

    if not records:
        print("nothing was translated, so nothing was established", file=sys.stderr)
        return 1

    agreed, output = check(generate_module(records))

    if verbose:
        for name in accepted:
            print(f"  checked  {name}")
        print()

    print(f"checked   {len(records)} of {len(runnable)} runnable examples "
          f"({len(records) / len(runnable):.0%})")
    print(f"  {'AGREE' if agreed else 'DISAGREE'}")

    # Attribution -- which rules decided, not merely what was decided. The second number is the
    # one that matters: the rest are forced by the verdict and prove nothing on their own.
    print(f"\nattribution checked on {decisions} decisions, of which {informative} are not "
          f"forced\n  by the verdict alone (an ALLOW among several permits, or any DENY where a "
          f"forbid exists)")

    print(f"\nrefused {sum(refused.values())}:")
    for reason, n in refused.most_common(12):
        print(f"  {n:4d}  {reason}")

    if not agreed:
        for line in output.splitlines():
            if "DISAGREEMENT" in line:
                print(f"\n{line.strip()}")
        print("\nA disagreement here is ours: both sides read the same policy and the same trace.",
              file=sys.stderr)
        return 1

    print(f"\nour reading agrees with Dogwood on every example it can translate. These are whole\n"
          f"policies written to demonstrate the language, so the refusal count is the honest\n"
          f"measure of how much of a real policy set the checker can take.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
