"""Differential test: does our TLA+ reading of Dogwood agree with Dogwood?

`specs/policy/TemporalPolicy` models `formerly within` from the AgentCore documentation. Documentation is a
paraphrase, and a spec built on a misread paraphrase does not fail — it verifies, and it verifies
something nobody is running. That is the same gap `cedar_differential.py` exists to close for Cedar,
and it was the largest caveat in the TemporalPolicy README.

Dogwood's own repository closes it. Its temporal regression corpus is 521 cases, each pairing a
policy set and an event trace with **the verdicts their engine produced**:

    corpus case ──┬── policy_*.dw ──> TLA+ policy data ──┐
                  ├── trace_N.log ──> TLA+ trace data ───┼──> TLC checks Agree
                  └── expected_N.out ─────────────────────┘   (the oracle)

No Rust is built and nothing is run from that tree — the expected outputs are recorded, so the
corpus is usable as data. That also keeps this harness inside the same no-network, no-credentials
property as the rest of the suite.

What is trusted by reading, and what is not:

  - DogwoodSemantics.tla   hand-written, reviewed once. The thing under test.
  - the parser below       also under test — a mistranslation surfaces as a disagreement exactly as
                           a semantics error would.
  - the expected outputs   not trusted, measured. They are Dogwood's own answers.

THE SUBSET. `formerly within`, `previous within` and `since within`, combined with `&&` and `!`,
under `when temporal` or `unless temporal`. Binds may join a past event's field to the request's
input, to a scope entity, to a literal, or to `_`. The grammar is parsed by recursive descent in
`translator.parse`, not by regex — it nests.

Aggregations are covered too — `count` and `sum` over `for (v: T)` binders, with `tp(t)` binding a
timepoint, in the `exists (n: T). (AGG == n && n CMP k)` shape the corpus uses throughout. That
shape says nothing more than `AGG CMP k` and is recognised as such; general existential
quantification is refused.

Anything else is REFUSED rather than guessed at, because a translator that quietly mishandles a
construct produces a disagreement it cannot attribute. The run reports how many cases were refused
and why.

**None of `since`, `previous` or the aggregations has documented semantics that we could find.**
They are written as standard past-time MFOTL, and the corpus is the only reason to believe that
reading. Every one of them is exercised by accepted cases and mutation-checked independently.

    python tests/strands/dogwood_differential.py
"""

from __future__ import annotations

import collections
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"
CORPUS = (REPO / "ext" / "dogwood" / "dogwood-language"
          / "tests" / "passing" / "temporal_only" / "corpus")

sys.path.insert(0, str(REPO / "src"))

from translator import (Unsupported, apply_pins, parse_policies, parse_schema, parse_trace,  # noqa: E402
                        policy_seq, run_tlc, stamp_keys, tla_record, tla_scalar, tla_value)


def parse_expected(text: str) -> dict[int, bool]:
    """`@20 (time point 6): false` -> {7: FALSE}. TLA+ sequences are 1-based."""
    oracle = {}
    for m in re.finditer(r"@\d+ \(time point (\d+)\):\s*(true|false)", text):
        oracle[int(m.group(1)) + 1] = m.group(2) == "true"
    if not oracle:
        raise Unsupported("no expected verdicts parsed")
    return oracle


def case_record(name: str, policies: list[dict], trace: list[dict],
                oracle: dict[int, bool],
                rules: dict[int, set[int]] | None = None) -> str:
    """One case as a TLA+ record.

    `rules` is the per-decision set of DETERMINING policy indices, 1-based to match the spec's
    policy sequence. It is optional because the unit corpus records no attribution; omitted, it
    becomes the empty function and the attribution check passes vacuously.
    """
    events = ", ".join(
        f'[time |-> {e["time"]}, action |-> "{e["action"]}", kind |-> "{e["kind"]}", '
        f'input |-> {tla_record(e["input"])}, output |-> {tla_record(e["output"])}, '
        f'principal |-> {tla_scalar(e["principal"])}, resource |-> {tla_scalar(e["resource"])}, '
        f'session |-> {tla_scalar(e["session"])}, '
        f'pins |-> {tla_record(e["pins"])}, '
        f'isDecision |-> {tla_value(e["decision"])}]'
        for e in trace)

    pols = policy_seq(policies, indent="", sep=", ")

    orc = " @@ ".join(f"{i} :> {tla_value(v)}" for i, v in sorted(oracle.items()))

    # `<< >>` is the empty function, which is what "this corpus records no attribution" means.
    # An empty SET for one decision is different and is a real claim: nothing matched, so the
    # deny is by default.
    rul = (" @@ ".join(f"{i} :> {{{', '.join(str(r) for r in sorted(rs))}}}"
                       for i, rs in sorted(rules.items()))
           if rules else "")

    # The domain a bound variable of non-Timepoint type ranges over: every scalar the trace
    # actually contains. Finite, so TLC can enumerate the assignments.
    vals = sorted({v for e in trace for rec in (e["input"], e["output"]) for v in rec.values()},
                  key=lambda x: (type(x).__name__, x))
    values = ", ".join(tla_scalar(v) for v in vals)

    return (f'    [name |-> "{name}", trace |-> <<{events}>>, '
            f'policies |-> <<{pols}>>, oracle |-> ({orc}), '
            f'rules |-> {f"({rul})" if rul else "<< >>"}, '
            f'values |-> {{{values}}}]')


def generate_module(cases: list[str]) -> str:
    """One module holding every case, so the corpus costs one TLC run rather than one each."""
    return """\\* GENERATED by tests/strands/dogwood_differential.py -- do not edit.
\\* Policies and traces translated from the Dogwood temporal corpus; each `oracle` is
\\* that case's recorded expected output, i.e. what the reference engine returned.
------------------------- MODULE DogwoodCases -------------------------
EXTENDS Integers, Sequences, TLC

\\* The empty attribute record. An event with no `input:` carries no fields at all,
\\* which is different from carrying fields that are empty.
EmptyRec == [f \\in {} |-> ""]

Cases ==
  <<
""" + ",\n".join(cases) + """
  >>

S == INSTANCE DogwoodSemantics

VARIABLE done
Init == done = FALSE
Next == UNCHANGED done
Spec == Init /\\ [][Next]_done

Agree == S!Agree

=============================================================================
"""


CONFIG = """\
SPECIFICATION Spec
CHECK_DEADLOCK FALSE
INVARIANT Agree
"""


def check(module_text: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="anchor-dogwood-") as tmp:
        work = Path(tmp)
        (work / "DogwoodCases.tla").write_text(module_text, encoding="utf-8")
        (work / "DogwoodCases.cfg").write_text(CONFIG, encoding="utf-8")
        (work / "DogwoodSemantics.tla").write_text(
            (SPECS / "DogwoodSemantics.tla").read_text(encoding="utf-8"), encoding="utf-8")

        return run_tlc("DogwoodCases", work, work)


# ------------------------------------------------------------------------------------------------
def collect_disagreements(output: str) -> list[str]:
    """Each disagreement as one line, gathered from the tuple TLC wraps across several.

    The Assert carries the case, the decision index and both verdicts. Matching only the line the
    word "DISAGREEMENT" lands on throws all of that away and leaves `<< "DISAGREEMENT",`.
    """
    lines, out, i = output.splitlines(), [], 0
    while i < len(lines):
        if "DISAGREEMENT" not in lines[i]:
            i += 1
            continue
        parts = []
        while i < len(lines):
            parts.append(lines[i].strip())
            if ">>" in lines[i]:
                break
            i += 1
        out.append(" ".join(parts).replace('"DISAGREEMENT",', "").replace("<<", "").strip())
        i += 1
    return out


def main() -> int:
    if not CORPUS.is_dir():
        print(f"corpus not found at {CORPUS}\n"
              "It ships with the Dogwood source; see the ledger in reference/README.md.",
              file=sys.stderr)
        return 2

    cases = sorted(c for c in CORPUS.iterdir() if c.is_dir())
    print(f"{len(cases)} cases in the Dogwood temporal corpus\n")

    refused: collections.Counter[str] = collections.Counter()
    records: list[str] = []
    pairs = 0

    for case in cases:
        try:
            # A custom event schema can PIN a field, injecting a correlation into every predicate
            # for every event -- a constraint the policy text never mentions and cannot bypass.
            # Case 1117 is the demonstration: bob logs in claiming to be alice, the written
            # condition matches, and the pin on `callerPrincipal` denies it anyway.
            #
            # So a policy's meaning is not determined by its own text. Reading the `.dw` alone and
            # ignoring the schema is precisely the silent mishandling this harness exists to avoid,
            # and it is why these are refused rather than approximated.
            schema_file = case / "event.dwschema"
            schema = (parse_schema(schema_file.read_text(encoding="utf-8"))
                      if schema_file.exists() else {"keys": [], "partial": {}})

            policies = parse_policies(
                "\n".join(p.read_text(encoding="utf-8") for p in sorted(case.glob("*.dw"))))

            # A partial pin is an ordinary conjunct on the kinds that declare it; a universal one
            # is a partition key stamped onto every term. Both happen here, at translation time,
            # so the policy records TLC evaluates already carry what the schema injected.
            apply_pins(policies, schema)
            if schema["keys"]:
                stamp_keys(policies, schema["keys"])
            parsed = []
            for tf in sorted(case.glob("trace_*.log")):
                ef = case / tf.name.replace("trace_", "expected_").replace(".log", ".out")
                if not ef.exists():
                    raise Unsupported("trace without expected output")
                parsed.append((parse_trace(tf.read_text(encoding="utf-8"), schema.get("paths")),
                               parse_expected(ef.read_text(encoding="utf-8"))))
        except Unsupported as e:
            refused[re.sub(r"'[^']*'", "...", e.kind)[:52]] += 1
            continue

        for n, (trace, oracle) in enumerate(parsed, 1):
            records.append(case_record(f"{case.name}#{n}", policies, trace, oracle))
            pairs += 1

    used_cases = len(cases) - sum(refused.values())
    if pairs == 0:
        print("nothing was translated, so nothing was established", file=sys.stderr)
        return 1

    agreed, output = check(generate_module(records))
    disagreements = collect_disagreements(output)

    print(f"checked   {pairs} (trace, expected) pairs from {used_cases} cases, in one TLC run")
    print(f"  {'AGREE' if agreed else 'DISAGREE'}")
    print(f"\nrefused {sum(refused.values())} cases, outside the modelled subset:")
    for reason, n in refused.most_common(12):
        print(f"  {n:4d}  {reason}")

    if not agreed:
        print("\ndisagreements:")
        for d in disagreements[:10]:
            print(f"  {d}")
        if not disagreements:
            print(output[-800:])
        return 1

    print(f"\nour reading of Dogwood's temporal operators agrees with the reference\n"
          f"implementation on all {pairs} pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
