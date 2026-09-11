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
`dogwood_parse.py`, not by regex — it nests.

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
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"
CORPUS = (REPO / "ext" / "dogwood" / "dogwood-language"
          / "tests" / "passing" / "temporal_only" / "corpus")

from _toolchain import find_jar  # noqa: E402

# `@N` in a trace is seconds, fixed by corpus case 0127: a read 12s after a login is denied under a
# `within 10s` window and one 8s after is allowed.
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


from dogwood_parse import (Dec, Unsupported, WILDCARD,  # noqa: E402
                           parse_decimal, parse_policies)
from dogwood_schema import apply_pins, parse_schema  # noqa: E402


def split_binds(text: str) -> list[str]:
    """Split on commas that are not inside quotes, honouring backslash escapes."""
    out, quoted, cur, esc = [], False, "", False
    for ch in text:
        if esc:
            esc = False
            cur += ch
            continue
        if ch == '\\':
            esc = True
            cur += ch
            continue
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
        # A backslash escapes the next character. Without this an escaped quote inside a
        # value -- `user: "o\\"brien"` -- read as CLOSING the string, so every
        # brace after it was treated as quoted and the scan ran to the end of the line.
        if c == '\\':
            i += 2
            continue
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
        # An entity reference is written bare -- `Drupe::Grant_Input_role::"reader"` -- and a
        # decimal as a bare `0.5`, where the policy writes `decimal("0.5")`.
        m = re.fullmatch(
            r'\s*(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|true|false|-?\d+\.\d+|-?\d+|[A-Za-z_]\w*(?:::\w+)*::"[^"]*")\s*',
            part)
        if not m:
            raise Unsupported(f"field {part.strip()[:32]!r} is not a scalar")
        k, v = m.group(1), m.group(2)
        # TLA+ string literals are ASCII. A value carrying anything else -- the corpus has a
        # JSON blob with an emoji in it -- would be emitted into a module SANY cannot lex, so
        # the case is refused here where the reason can still be stated.
        if not v.isascii():
            raise Unsupported("field value is not ASCII, which a TLA+ string cannot carry")
        if v in ("true", "false"):
            fields[k] = v == "true"
        elif v.startswith('"'):
            # A string may carry an escaped quote -- `"o\"brien"` -- so the escapes come back out.
            fields[k] = v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        elif "::" in v:
            # Compared as its written form, which is what the policy writes too.
            fields[k] = v
        elif "." in v:
            fields[k] = parse_decimal(v)
        else:
            n = int(v)
            # Dogwood's `Long` outruns TLC, which works in Java ints and stops with
            # "TLC can't handle a number this big" rather than giving a wrong answer.
            if abs(n) > 2**31 - 1:
                raise Unsupported("field value outside TLC's integer range")
            fields[k] = n
    return fields


def pin_value(rest: str, path: str) -> str:
    """One pinned field's value, read from the event's own payload.

    `tenant_id` is a top-level scalar; `__drupe.session_id` is a leaf inside a record group. Both
    are read from the payload rather than from the decision's `request_context(...)` envelope --
    for a decision event the two carry the same value, checked across the corpus.
    """
    if "." in path:
        group, leaf = path.split(".", 1)
        m = re.search(r"\b" + re.escape(group) + r":\s*\{", rest)
        return parse_fields(braced(rest, m.end() - 1)[0]).get(leaf, "") if m else ""
    m = re.search(re.escape(path) + r':\s*"([^"]*)"', rest)
    return m.group(1) if m else ""


def parse_trace(text: str, paths: dict[str, str] | None = None) -> list[dict]:
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
            # The reserved group a schema can pin a leaf of. Read from the event's OWN payload,
            # like input and output -- for a decision event that is the same value its
            # `request_context` carries, checked across every such event in the corpus.
            "session": section("__drupe").get("session_id", ""),
            # Only the fields this case's schema actually pins. An event carries plenty more,
            # and modelling what no policy reads would cost state space for nothing.
            "pins": {k: pin_value(rest, p) for k, p in (paths or {}).items()},
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


def tla_scalar(v) -> str:
    """A field value, tagged with its kind so TLC never compares across kinds."""
    if isinstance(v, bool):
        return f'[k |-> "b", v |-> {"TRUE" if v else "FALSE"}]'
    # Before the `int` arm: Dec subclasses int, and a decimal must never compare equal to a
    # Long that happens to share its scaled value.
    if isinstance(v, Dec):
        return f'[k |-> "d", v |-> {int(v)}]'
    if isinstance(v, int):
        return f'[k |-> "n", v |-> {v}]'
    escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'[k |-> "s", v |-> "{escaped}"]'


def tla_record(fields: dict) -> str:
    if not fields:
        return 'EmptyRec'
    return "[" + ", ".join(f"{k} |-> {tla_scalar(v)}" for k, v in sorted(fields.items())) + "]"


def tla_pred(pd: dict) -> str:
    def bind(b):
        return (f'[side |-> "{b["side"]}", field |-> "{b["field"]}", kind |-> "{b["kind"]}", '
                f'name |-> "{b["name"]}", value |-> {tla_scalar(b["value"])}]')
    return (f'[action |-> "{pd["action"]}", kind |-> "{pd["kind"]}", '
            f'binds |-> <<{", ".join(bind(b) for b in pd["binds"])}>>]')


DUMMY_PRED = '[action |-> "", kind |-> "", binds |-> <<>>]'


# Every atom carries every field, unused ones filled in. One record shape rather than a union:
# TLC treats a missing field as a runtime error, so uniformity is cheaper than the alternative.
NO_CMP = ('field |-> "", cmp |-> "", value |-> [k |-> "s", v |-> ""], other |-> "", '
          'pattern |-> <<>>')

# A TLA+ string literal cannot carry a raw newline or a bare backslash, so a pattern character is
# written the way the language spells it. Anything unprintable has no TLA+ spelling at all and is
# refused rather than mangled into something that would match the wrong thing.
TLA_CHAR_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t",
                    "\r": "\\r", "\f": "\\f"}


def tla_pattern(pattern: list) -> str:
    """A `like` pattern as a sequence of [wild, c] records, which `Matches` walks.

    A wildcard is not a character and cannot be smuggled into a string, so it gets its own flag
    rather than a reserved character that a policy could then never match literally.
    """
    out = []
    for e in pattern:
        if e is WILDCARD:
            out.append('[wild |-> TRUE, c |-> ""]')
        elif e in TLA_CHAR_ESCAPES:
            out.append(f'[wild |-> FALSE, c |-> "{TLA_CHAR_ESCAPES[e]}"]')
        elif e.isprintable():
            out.append(f'[wild |-> FALSE, c |-> "{e}"]')
        else:
            raise Unsupported(
                f"a `like` pattern contains U+{ord(e):04X}, which a TLA+ string cannot carry")
    return f'<<{", ".join(out)}>>' 


def tla_atom(a: dict) -> str:
    """Atoms are uniform — every node carries pred, var, args and the comparison fields."""
    if a["op"] == "pred":
        return (f'[op |-> "pred", pred |-> {tla_pred(a["pred"])}, var |-> "", args |-> <<>>, '
                f'{NO_CMP}]')
    if a["op"] == "tp":
        return (f'[op |-> "tp", pred |-> {DUMMY_PRED}, var |-> "{a["var"]}", args |-> <<>>, '
                f'{NO_CMP}]')
    if a["op"] == "like":
        # The pattern travels to TLC, which evaluates it against the field's actual value.
        # Nothing about the match is decided here.
        return (f'[op |-> "like", pred |-> {DUMMY_PRED}, var |-> "", args |-> <<>>, '
                f'field |-> "{a["field"]}", cmp |-> "", '
                f'value |-> [k |-> "s", v |-> ""], other |-> "", '
                f'pattern |-> {tla_pattern(a["pattern"])}]')
    if a["op"] == "cmp":
        return (f'[op |-> "cmp", pred |-> {DUMMY_PRED}, var |-> "", args |-> <<>>, '
                f'field |-> "{a["field"]}", cmp |-> "{a["cmp"]}", '
                f'value |-> {tla_scalar(a["value"])}, other |-> "", pattern |-> <<>>]')
    if a["op"] == "cmp2":
        return (f'[op |-> "cmp2", pred |-> {DUMMY_PRED}, var |-> "", args |-> <<>>, '
                f'field |-> "{a["field"]}", cmp |-> "{a["cmp"]}", '
                f'value |-> [k |-> "s", v |-> ""], other |-> "{a["other"]}", '
                f'pattern |-> <<>>]')
    if a["op"] == "cmpvar":
        return (f'[op |-> "cmpvar", pred |-> {DUMMY_PRED}, var |-> "{a["var"]}", args |-> <<>>, '
                f'field |-> "", cmp |-> "{a["cmp"]}", '
                f'value |-> {tla_scalar(a["value"])}, other |-> "", pattern |-> <<>>]')
    # The op travels with the node. This used to be hardcoded to "and", which silently turned
    # a `not` atom into a conjunction of its single argument -- so `!(B)` read as `B`.
    args = ", ".join(tla_atom(x) for x in a["args"])
    return (f'[op |-> "{a["op"]}", pred |-> {DUMMY_PRED}, var |-> "", args |-> <<{args}>>, '
            f'{NO_CMP}]')


DUMMY_ATOM = f'[op |-> "pred", pred |-> {DUMMY_PRED}, var |-> "", args |-> <<>>, {NO_CMP}]'
DUMMY_TERM = (f'[op |-> "formerly", window |-> 0, atom |-> {DUMMY_ATOM}, '
              f'left |-> {DUMMY_ATOM}, leftNeg |-> FALSE, keys |-> <<>>]')


def stamp_keys(policies: list[dict], keys: list[str]) -> None:
    """Put the partition keys on every term, in place.

    Carried on the term rather than threaded through `TermHolds`'s signature because a pin is a
    schema-level fact that applies uniformly -- every term in the policy set gets the same keys,
    so a parameter would be the same value repeated down every call.
    """
    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        if node.get("op") in ("formerly", "previous", "since", "at") and "window" in node:
            node["keys"] = keys
        for key in ("term", "atom", "left", "cond", "agg"):
            walk(node.get(key))
        for child in node.get("args", []) or []:
            walk(child)

    for p in policies:
        walk(p["cond"])


def tla_cond(c: dict) -> str:
    """Condition nodes carry `term` always; `agg` only where there is one.

    An aggregation holds a condition which could hold another aggregation, so a dummy `agg`
    cannot be written down without recursing forever. The `agg` arm of CondHolds is only
    reached when op = "agg", and TLA+ evaluates just the selected CASE arm.
    """
    if c["op"] == "term":
        t = c["term"]
        keys = ", ".join(f'"{k}"' for k in t.get("keys", []))
        term = (f'[op |-> "{t["op"]}", window |-> {t["window"]}, atom |-> {tla_atom(t["atom"])}, '
                f'left |-> {tla_atom(t["left"])}, leftNeg |-> {tla_value(t["leftNeg"])}, '
                f'keys |-> <<{keys}>>]')
        return f'[op |-> "term", args |-> <<>>, term |-> {term}]'

    if c["op"] == "exists":
        a = c["agg"]
        binders = ", ".join(f'[name |-> "{b["name"]}", type |-> "{b["type"]}"]'
                            for b in a["binders"])
        agg = (f'[kind |-> "{a["kind"]}", over |-> "{a["over"]}", '
               f'binders |-> <<{binders}>>, cond |-> {tla_cond(a["cond"])}]')
        return (f'[op |-> "exists", args |-> <<>>, term |-> {DUMMY_TERM}, agg |-> {agg}, '
                f'cmp |-> "", value |-> 0]')

    if c["op"] == "agg":
        a = c["agg"]
        binders = ", ".join(f'[name |-> "{b["name"]}", type |-> "{b["type"]}"]'
                            for b in a["binders"])
        agg = (f'[kind |-> "{a["kind"]}", over |-> "{a["over"]}", '
               f'binders |-> <<{binders}>>, cond |-> {tla_cond(a["cond"])}]')
        return (f'[op |-> "agg", args |-> <<>>, term |-> {DUMMY_TERM}, agg |-> {agg}, '
                f'cmp |-> "{c["cmp"]}", value |-> {c["value"]}]')

    args = ", ".join(tla_cond(a) for a in c.get("args", []))
    return f'[op |-> "{c["op"]}", args |-> <<{args}>>, term |-> {DUMMY_TERM}]'


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

    pols = ", ".join(
        f'[effect |-> "{p["effect"]}", action |-> "{p["action"]}", cond |-> {tla_cond(p["cond"])}]'
        for p in policies)

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

        proc = subprocess.run(
            # Its own java temp dir. TLC unpacks the standard modules there, and parallel
            # runs sharing one leave a half-written `Naturals.tla` behind, which SANY reports as
            # a failure in whichever unrelated spec lost the race -- about one run in four. Same
            # fix, and same reason, as `TLCProcess.cs`.
            ["java", f"-Djava.io.tmpdir={work}",
             "-cp", str(find_jar()), "tlc2.TLC", "-cleanup",
             "-metadir", str(work / "states"), "-config", "DogwoodCases.cfg", "DogwoodCases.tla"],
            cwd=work, capture_output=True, text=True,
        )
        return proc.returncode == 0, proc.stdout + proc.stderr


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
