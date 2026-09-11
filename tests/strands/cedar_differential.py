"""Differential test: does our TLA+ model of Cedar agree with the real Cedar engine?

The problem this addresses. A TLA+ spec of someone else's code is a paraphrase — nothing checks
that it describes the real thing, and a wrong model does not fail, it verifies. Translating a
declarative artifact is better, because the same file drives both sides, but the translator itself
is still hand-written and can be wrong.

So: don't trust the translation, test it. Enumerate the whole finite request space, ask both the
model and the real engine for a decision on every request, and compare. TLC does the comparison,
so a disagreement comes back as a counterexample naming the exact request.

    policies.cedar ──┬── translate ──> TLA+ policy data ──┐
                     │                                     ├──> TLC checks Agree
                     └── cedarpy ────> oracle table ──────┘

What is trusted by reading, and what is not:

  - CedarSemantics.tla    hand-written, reviewed once. The thing under test.
  - the translator below  hand-written. Also under test — a mistranslation shows up as a
                          disagreement exactly like a semantics error would.
  - the oracle            not trusted, measured. It is the real engine's answer.

Requires cedarpy, which is pinned and hash-locked like everything else — see requirements/strands/README.md.
A bare ``pip install cedarpy`` would bypass hash checking; recompile the lock instead.

    python tests/strands/cedar_differential.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "cedar"
JAR = REPO / "lib" / "tla2tools-1.7.4.jar"

# The finite domain the two sides are compared over. Small enough to enumerate exhaustively,
# wide enough that the interesting boundaries (the call_count < 3 threshold, the forbid that
# shadows the admin permit) fall inside it.
PRINCIPALS = [("User", "alice"), ("User", "bob"), ("Admin", "root")]
ACTIONS = ["search", "read_file", "delete_file", "send_email"]
CALL_COUNTS = [0, 1, 2, 3, 4]


class Unsupported(Exception):
    """The .cedar file uses a construct the translator does not model.

    Raised rather than guessed at. A translator that silently mishandles a construct produces a
    model that disagrees with reality in a way the differential test cannot attribute.
    """


# --------------------------------------------------------------------------------------------
# Translation: policies.cedar -> TLA+ policy data
# --------------------------------------------------------------------------------------------
@dataclass
class Policy:
    effect: str
    principal: dict = field(default_factory=lambda: {"kind": "any"})
    action: dict = field(default_factory=lambda: {"kind": "any"})
    conditions: list[dict] = field(default_factory=list)


_OPS = {"<": "lt", "<=": "lte", ">": "gt", ">=": "gte", "==": "eq"}


def _strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def parse_cedar(text: str) -> list[Policy]:
    """Translate the modelled subset. Anything else raises."""
    policies: list[Policy] = []

    for raw in [s.strip() for s in _strip_comments(text).split(";") if s.strip()]:
        m = re.match(r"^(permit|forbid)\s*\((.*?)\)\s*(.*)$", raw, re.S)
        if not m:
            raise Unsupported(f"not a permit/forbid statement: {raw[:60]!r}")

        effect, scope_text, tail = m.group(1), m.group(2), m.group(3).strip()
        policy = Policy(effect=effect)

        scopes = [s.strip() for s in scope_text.split(",")]
        if len(scopes) != 3:
            raise Unsupported(f"expected principal, action, resource; got {scopes!r}")

        principal, action, resource = scopes

        if principal != "principal":
            pm = re.match(r'^principal\s*==\s*(\w+)::"([^"]+)"$', principal)
            pt = re.match(r"^principal\s+is\s+(\w+)$", principal)
            if pm:
                policy.principal = {"kind": "eq", "entity": {"type": pm.group(1), "id": pm.group(2)}}
            elif pt:
                policy.principal = {"kind": "type", "entityType": pt.group(1)}
            else:
                raise Unsupported(f"principal scope: {principal!r}")

        if action != "action":
            am = re.match(r'^action\s*==\s*Action::"([^"]+)"$', action)
            ain = re.match(r"^action\s+in\s*\[(.*)\]$", action, re.S)
            if am:
                policy.action = {"kind": "eq", "name": am.group(1)}
            elif ain:
                names = re.findall(r'Action::"([^"]+)"', ain.group(1))
                if not names:
                    raise Unsupported(f"action in-list: {action!r}")
                policy.action = {"kind": "in", "names": names}
            else:
                raise Unsupported(f"action scope: {action!r}")

        # Strands hardcodes Resource::"agent" on every request, so a resource-scoped policy could
        # never match anything the handler sends. Refuse rather than model it as unconstrained.
        if resource != "resource":
            raise Unsupported(
                f"resource scope {resource!r}: the Strands handler always sends "
                'Resource::"agent", so resource-scoped policies are unreachable through it'
            )

        if tail:
            for cond in re.finditer(r"when\s*\{(.*?)\}", tail, re.S):
                body = cond.group(1).strip()
                cm = re.match(r"^context\.session\.call_count\s*(<=|>=|==|<|>)\s*(\d+)$", body)
                if not cm:
                    raise Unsupported(f"condition: {body!r}")
                policy.conditions.append({"op": _OPS[cm.group(1)], "value": int(cm.group(2))})
            if not policy.conditions:
                raise Unsupported(f"trailing text that is not a when clause: {tail[:60]!r}")

        policies.append(policy)

    return policies


# --------------------------------------------------------------------------------------------
# The oracle: the real engine's decision for every request in the domain
# --------------------------------------------------------------------------------------------
def build_oracle(policy_text: str) -> dict[tuple[str, str, str, int], str]:
    import cedarpy

    oracle = {}
    for ptype, pid in PRINCIPALS:
        for action in ACTIONS:
            for count in CALL_COUNTS:
                request = {
                    "principal": f'{ptype}::"{pid}"',
                    "action": f'Action::"{action}"',
                    "resource": 'Resource::"agent"',
                    "context": {"session": {"call_count": count, "hour_utc": 12}},
                }
                result = cedarpy.is_authorized(request, policy_text, [])
                oracle[(ptype, pid, action, count)] = "Allow" if result.allowed else "Deny"
    return oracle


# --------------------------------------------------------------------------------------------
# Emit the generated TLA+ module and check it
# --------------------------------------------------------------------------------------------
def _tla_scope(scope: dict) -> str:
    if scope["kind"] == "any":
        return '[kind |-> "any"]'
    if scope["kind"] == "eq" and "entity" in scope:
        e = scope["entity"]
        return f'[kind |-> "eq", entity |-> [type |-> "{e["type"]}", id |-> "{e["id"]}"]]'
    if scope["kind"] == "type":
        return f'[kind |-> "type", entityType |-> "{scope["entityType"]}"]'
    if scope["kind"] == "eq":
        return f'[kind |-> "eq", name |-> "{scope["name"]}"]'
    if scope["kind"] == "in":
        names = ", ".join(f'"{n}"' for n in scope["names"])
        return f'[kind |-> "in", names |-> {{{names}}}]'
    raise Unsupported(f"scope: {scope!r}")


def generate_module(policies: list[Policy], oracle: dict) -> str:
    pol_entries = []
    for p in policies:
        conds = ", ".join(f'[op |-> "{c["op"]}", value |-> {c["value"]}]' for c in p.conditions)
        pol_entries.append(
            f'    [effect |-> "{p.effect}", '
            f"principal |-> {_tla_scope(p.principal)}, "
            f"action |-> {_tla_scope(p.action)}, "
            f"conditions |-> <<{conds}>>]"
        )

    oracle_entries = [
        f'    [principal |-> [type |-> "{t}", id |-> "{i}"], action |-> "{a}", callCount |-> {c}]'
        f' :> "{d}"'
        for (t, i, a, c), d in sorted(oracle.items())
    ]

    principals = ", ".join(f'[type |-> "{t}", id |-> "{i}"]' for t, i in PRINCIPALS)
    actions = ", ".join(f'"{a}"' for a in ACTIONS)
    counts = ", ".join(str(c) for c in CALL_COUNTS)

    return f"""\\* GENERATED by tests/strands/cedar_differential.py -- do not edit.
\\* Policies translated from policies.cedar; Oracle measured from the real cedarpy engine.
---------------------------- MODULE CedarDifferential ----------------------------
EXTENDS Naturals, Sequences, TLC

PrincipalSet == {{{principals}}}
ActionSet == {{{actions}}}
CallCountSet == {{{counts}}}

Policies ==
  <<
{",\n".join(pol_entries)}
  >>

Oracle ==
  (
{" @@\n".join(oracle_entries)}
  )

S == INSTANCE CedarSemantics

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
    (SPECS / "CedarDifferential.tla").write_text(module_text, encoding="utf-8")
    (SPECS / "CedarDifferential.cfg").write_text(CONFIG, encoding="utf-8")

    proc = subprocess.run(
        ["java", "-cp", str(JAR), "tlc2.TLC", "-cleanup",
         "-config", "CedarDifferential.cfg", "CedarDifferential.tla"],
        cwd=SPECS, capture_output=True, text=True,
    )
    return proc.returncode == 0, proc.stdout + proc.stderr


def main() -> int:
    policy_text = (SPECS / "policies.cedar").read_text(encoding="utf-8")

    try:
        policies = parse_cedar(policy_text)
    except Unsupported as e:
        print(f"translator refused: {e}", file=sys.stderr)
        return 2
    print(f"translated {len(policies)} policies from policies.cedar")

    try:
        oracle = build_oracle(policy_text)
    except ImportError:
        print(
            "cedarpy is not installed, so there is no engine to compare against.\n"
            "It is pinned in requirements/strands/requirements.in. Recompile and install rather\n"
            "reaching for a bare pip install, which would skip hash checking:\n"
            "  than reaching for a bare pip install, which would skip hash checking:\n"
            "  python/Scripts/uv.exe pip compile requirements/strands/requirements.in \\\n"
            "      --universal --python-version 3.13 --generate-hashes \\\n"
            "      -o requirements/strands/requirements.txt\n"
            "  requirements\\strands\\install.cmd",
            file=sys.stderr,
        )
        return 2
    print(f"measured {len(oracle)} decisions from the real engine")

    agreed, output = check(generate_module(policies, oracle))
    if agreed:
        print(f"AGREE on all {len(oracle)} requests")
        return 0

    print("DISAGREE — TLC output follows:\n")
    print(output)
    return 1


if __name__ == "__main__":
    sys.exit(main())
