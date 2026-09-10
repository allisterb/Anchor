"""Differential test: does our TLA+ reading of Dogwood agree with Dogwood?

`specs/TemporalPolicy` models `formerly within` from the AgentCore documentation. Documentation is a
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
`dogwood_parse.py`, not by regex — it nests.

Anything else is REFUSED rather than guessed at, because a translator that quietly mishandles a
construct produces a disagreement it cannot attribute. The run reports how many cases were refused
and why. The largest refusal by far is `count`/`sum`, which are quantified aggregations with
variable binders, `exists` and `tp()` markers: a sub-language big enough that approximating it
would be guessing.

`since` and `previous` are written as standard past-time MFOTL because **their semantics are not
documented anywhere we could find**. That reading is checked here against 66 and 29 corpus cases
respectively, which is the only reason to believe it.

    python tests/strands/dogwood_differential.py
"""

from __future__ import annotations

import collections
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "TemporalPolicy"
JAR = REPO / "lib" / "tla2tools-1.7.4.jar"
CORPUS = (REPO / "reference" / "projects" / "dogwood-main" / "dogwood-language"
          / "tests" / "passing" / "temporal_only" / "corpus")

# `@N` in a trace is seconds, fixed by corpus case 0127: a read 12s after a login is denied under a
# `within 10s` window and one 8s after is allowed.
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


from dogwood_parse import Unsupported, parse_policies  # noqa: E402


def split_binds(text: str) -> list[str]:
    """Split on commas that are not inside quotes."""
    out, quoted, cur = [], False, ""
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


# ------------------------------------------------------------------------------------------------
# Traces:  trace_N.log -> TLA+ trace data,  expected_N.out -> the oracle
# ------------------------------------------------------------------------------------------------
def braced(text: str, start: int) -> tuple[str, int]:
    """The balanced `{...}` beginning at `start`, and the index just past it.

    Not a regex, because a value can itself be an object — `config: { a: 1 }` — and a
    non-greedy `\\{([^}]*)\\}` silently truncates it mid-value rather than failing. That
    produced a mangled field, a broken TLA+ string literal, and an unparseable module,
    which is precisely the failure mode a translator must not have.
    """
    depth, i, quoted = 0, start, False
    while i < len(text):
        c = text[i]
        if c == '"':
            quoted = not quoted
        elif not quoted and c == "{":
            depth += 1
        elif not quoted and c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise Unsupported("unbalanced braces in a trace line")


def parse_fields(text: str) -> dict:
    """`{ server: "s1", user: "alice" }` -> a dict of scalars. Anything else is refused.

    Strict by construction: every top-level comma-separated part must be `name: scalar`.
    A structured value has no representation in the modelled subset, so the case is
    refused rather than approximated.
    """
    fields = {}
    for part in split_binds(text):
        if not part.strip():
            continue
        m = re.fullmatch(r'\s*(\w+)\s*:\s*("[^"]*"|true|false)\s*', part)
        if not m:
            raise Unsupported(f"field {part.strip()[:32]!r} is not a scalar")
        k, v = m.group(1), m.group(2)
        fields[k] = (v == "true") if v in ("true", "false") else v[1:-1]
    return fields


def parse_trace(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if not line.strip():
            continue
        tm = re.match(r"@(\d+)\s", line)
        am = re.search(r'(\w+)::Action::"([^"]+)"::(\w+)\(', line)
        if not tm or not am:
            raise Unsupported(f"trace line {line[:48]!r}")

        rest = line[am.end():]

        def section(name: str) -> dict:
            # `rest` starts after the action, so the earlier `request_context(input: ...)`
            # is already behind us; this finds the event's own attribute block.
            m = re.search(r"\b" + name + r":\s*\{", rest)
            return parse_fields(braced(rest, m.end() - 1)[0]) if m else {}

        # `scope(principal: NS::Type::"id", resource: NS::Type::"id")` -- needed by
        # `callerPrincipal: principal` binds, which compare a past event's caller against
        # the deciding request's scope.
        sc = re.search(r'scope\(principal:\s*([^,]+),\s*resource:\s*([^)]+)\)', line)
        events.append({
            "time": int(tm.group(1)),
            "action": am.group(2),
            "kind": am.group(3),
            "input": section("input"),
            "output": section("output"),
            "principal": sc.group(1).strip() if sc else "",
            "resource": sc.group(2).strip() if sc else "",
            "decision": "request_context(" in line,
        })
    return events


def parse_expected(text: str) -> dict[int, bool]:
    """`@20 (time point 6): false` -> {7: FALSE}. TLA+ sequences are 1-based."""
    oracle = {}
    for m in re.finditer(r"@\d+ \(time point (\d+)\):\s*(true|false)", text):
        oracle[int(m.group(1)) + 1] = m.group(2) == "true"
    if not oracle:
        raise Unsupported("no expected verdicts parsed")
    return oracle


# ------------------------------------------------------------------------------------------------
# Emit the generated module and check it
# ------------------------------------------------------------------------------------------------
def tla_value(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, int):
        return str(v)
    # Entity references carry their own quotes — `Drupe::OAuthUser::"alice"` — so a naive
    # f'"{v}"' closes the TLA+ literal early and the module stops parsing.
    escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def tla_record(fields: dict) -> str:
    if not fields:
        return 'EmptyRec'
    return "[" + ", ".join(f"{k} |-> {tla_value(v)}" for k, v in sorted(fields.items())) + "]"


def tla_pred(pd: dict) -> str:
    def bind(b):
        return (f'[side |-> "{b["side"]}", field |-> "{b["field"]}", kind |-> "{b["kind"]}", '
                f'name |-> "{b["name"]}", value |-> {tla_value(b["value"])}]')
    return (f'[action |-> "{pd["action"]}", kind |-> "{pd["kind"]}", '
            f'binds |-> <<{", ".join(bind(b) for b in pd["binds"])}>>]')


DUMMY_PRED = '[action |-> "", kind |-> "", binds |-> <<>>]'
DUMMY_TERM = (f'[op |-> "formerly", window |-> 0, pred |-> {DUMMY_PRED}, '
              f'left |-> {DUMMY_PRED}, leftNeg |-> FALSE]')


def tla_cond(c: dict) -> str:
    """Every node carries every field, so nothing depends on a CASE arm being lazy."""
    if c["op"] == "term":
        t = c["term"]
        term = (f'[op |-> "{t["op"]}", window |-> {t["window"]}, pred |-> {tla_pred(t["pred"])}, '
                f'left |-> {tla_pred(t["left"])}, leftNeg |-> {tla_value(t["leftNeg"])}]')
        return f'[op |-> "term", args |-> <<>>, term |-> {term}]'
    args = ", ".join(tla_cond(a) for a in c.get("args", []))
    return f'[op |-> "{c["op"]}", args |-> <<{args}>>, term |-> {DUMMY_TERM}]'


def case_record(name: str, policies: list[dict], trace: list[dict],
                oracle: dict[int, bool]) -> str:
    events = ", ".join(
        f'[time |-> {e["time"]}, action |-> "{e["action"]}", kind |-> "{e["kind"]}", '
        f'input |-> {tla_record(e["input"])}, output |-> {tla_record(e["output"])}, '
        f'principal |-> {tla_value(e["principal"])}, resource |-> {tla_value(e["resource"])}, '
        f'isDecision |-> {tla_value(e["decision"])}]'
        for e in trace)

    pols = ", ".join(
        f'[effect |-> "{p["effect"]}", action |-> "{p["action"]}", cond |-> {tla_cond(p["cond"])}]'
        for p in policies)

    orc = " @@ ".join(f"{i} :> {tla_value(v)}" for i, v in sorted(oracle.items()))

    return (f'    [name |-> "{name}", trace |-> <<{events}>>, '
            f'policies |-> <<{pols}>>, oracle |-> ({orc})]')


def generate_module(cases: list[str]) -> str:
    """One module holding every case, so the corpus costs one TLC run rather than one each."""
    return """\\* GENERATED by tests/strands/dogwood_differential.py -- do not edit.
\\* Policies and traces translated from the Dogwood temporal corpus; each `oracle` is
\\* that case's recorded expected output, i.e. what the reference engine returned.
------------------------- MODULE DogwoodCases -------------------------
EXTENDS Naturals, Sequences, TLC

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

        proc = subprocess.run(
            ["java", "-cp", str(JAR), "tlc2.TLC", "-cleanup",
             "-metadir", str(work / "states"), "-config", "DogwoodCases.cfg", "DogwoodCases.tla"],
            cwd=work, capture_output=True, text=True,
        )
        return proc.returncode == 0, proc.stdout + proc.stderr


# ------------------------------------------------------------------------------------------------
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
            if (case / "event.dwschema").exists():
                raise Unsupported("event schema pins a field into every predicate")

            policies = parse_policies(
                "\n".join(p.read_text(encoding="utf-8") for p in sorted(case.glob("*.dw"))))
            parsed = []
            for tf in sorted(case.glob("trace_*.log")):
                ef = case / tf.name.replace("trace_", "expected_").replace(".log", ".out")
                if not ef.exists():
                    raise Unsupported("trace without expected output")
                parsed.append((parse_trace(tf.read_text(encoding="utf-8")),
                               parse_expected(ef.read_text(encoding="utf-8"))))
        except Unsupported as e:
            refused[re.sub(r"'[^']*'", "...", str(e))[:52]] += 1
            continue

        for n, (trace, oracle) in enumerate(parsed, 1):
            records.append(case_record(f"{case.name}#{n}", policies, trace, oracle))
            pairs += 1

    used_cases = len(cases) - sum(refused.values())
    if pairs == 0:
        print("nothing was translated, so nothing was established", file=sys.stderr)
        return 1

    agreed, output = check(generate_module(records))
    disagreements = [ln.strip() for ln in output.splitlines() if "DISAGREEMENT" in ln]

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
