"""Differential test against the Dogwood engine itself, on traces we construct.

`dogwood_differential.py` checks our semantics against the reference corpus. That validates a lot —
911 pairs — but only over traces Amazon happened to record, and the corpus has a blind spot we care
about: across all 521 cases, `::error` appears in **zero** policies and **zero** traces.

That matters because the `error` event kind is exactly what `specs/policy/TemporalPolicy`'s findings rest
on. AgentCore records a denied action as an `error` rather than a `response`, which is why a permit
gated on `::response` goes vacuous when the action it depends on is forbidden, and why the same rule
written against `::request` does not. Until now that was documented and modelled but never executed.

The built `dogwood` binary closes it. Unlike the corpus it is a live oracle: it will judge any trace
we hand it, including ones with event kinds the corpus never uses.

    approval_gate_*.dw ──┬── dogwood replay ──────────────────────> verdicts (the oracle)
                         └── translator  ──> TLA+ data ──> TLC ──> our verdicts

Both sides read the same policy file, so a disagreement is ours. The three gates differ by exactly
one word -- `response`, `request`, `error` -- which is the point being made.

THE SECOND BLIND SPOT IS THE EVENT SCHEMA. A universal pin partitions the history a temporal
predicate can see, and no policy can observe or bypass one -- so the same policy text means
different things under different schemas. Dogwood ships four presets, and the corpus exercises the
pin shape of only one of them: `pin callerPrincipal` appears in 16 cases and a nested `__drupe`
leaf in 3, while `session-pinned.dwschema` -- one deployment flag from the default -- appears in
zero. `session_gate.dw` is replayed under two of the shipped presets, unchanged, and means
different things under each.

REQUIRES THE BUILT BINARY, which is not in the repo. Build it with:

    cargo build --release --locked --manifest-path ext/dogwood/Cargo.toml

and re-check that the `net` feature stayed out of it — see reference/README.md. Without the binary
this harness skips rather than pretending to pass.

    python tests/strands/dogwood_replay.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs" / "policy" / "TemporalPolicy"

# The policy fixtures live under tests/, not specs/, because they are inputs that demonstrate the
# tooling rather than models the project asserts things about. rotation_*.dw stayed in specs/ for
# exactly that reason: SessionRotation.tla is ABOUT those two.
POLICIES = REPO / "tests" / "policies"
SCHEMA = POLICIES / "anchor.cedarschema"
# `.exe` only on Windows. Hard-coding it would make this harness skip on a Linux runner even
# once the binary is built there, and a silent skip is worse than a loud failure.
DOGWOOD = (REPO / "ext" / "dogwood" / "target" / "release"
           / ("dogwood.exe" if sys.platform == "win32" else "dogwood"))

sys.path.insert(0, str(REPO / "src"))

from dogwood_differential import case_record, check, generate_module  # noqa: E402
from translator import (Unsupported, apply_pins, parse_policies,  # noqa: E402
                        parse_schema, parse_trace, stamp_keys)

# The event-schema presets Dogwood SHIPS, read from the pinned submodule rather than copied here.
# A copy would drift, and the point of these scenarios is agreement with what is actually shipped.
EVENT_SCHEMAS = (REPO / "ext" / "dogwood" / "dogwood-language" / "configuration" / "event-schemas")

SCOPE = 'scope(principal: Anchor::OAuthUser::"alice", resource: Anchor::Gateway::"gw1")'
CALLER = 'callerPrincipal: Anchor::OAuthUser::"alice", callerResource: Anchor::Gateway::"gw1"'


def approve(t: int, kind: str, session: str | None = None) -> str:
    # `sessionId` rides on the payload AND on the decision's context, which is where a
    # `pin sessionId = context.sessionId` reads its two sides from.
    sid = f', sessionId: "{session}"' if session else ""
    ctx = (f'request_context(input: {{ approver: "alice" }}{sid}) '
           if kind == "request" else "")
    return (f'@{t} {SCOPE} {ctx}Anchor::Action::"Approve"::{kind}'
            f'(input: {{ approver: "alice" }}, {CALLER}, requestId: "a{t}"{sid})')


def scored(t: int) -> list[str]:
    """A Score request and its response, whose output carries both a decimal and a Long."""
    return [
        f'@{t} {SCOPE} request_context(input: {{ user: "alice" }}) '
        f'Anchor::Action::"Score"::request(input: {{ user: "alice" }}, {CALLER}, '
        f'requestId: "s{t}")',
        f'@{t + 1} {SCOPE} Anchor::Action::"Score"::response(input: {{ user: "alice" }}, '
        f'output: {{ score: 0.9, count: 7 }}, {CALLER}, requestId: "s{t}")',
    ]


def trade(t: int, amount: int = 1, session: str | None = None) -> str:
    sid = f', sessionId: "{session}"' if session else ""
    return (f'@{t} {SCOPE} request_context(input: {{ amount: {amount} }}{sid}) '
            f'Anchor::Action::"Trade"::request(input: {{ amount: {amount} }}, '
            f'{CALLER}, requestId: "t{t}"{sid})')


# The policies are checked-in Dogwood text, not strings built here, so the artifact the finding
# rests on can be read without reading this file. Both sides below read the same path: the engine
# is handed it directly, and our translation parses the same bytes.
#
# The traces stay generated. They are scaffolding -- a history to evaluate against -- where the
# policies are the thing under test.
#
# Each scenario is a region the recorded corpus does not reach. The `why` is the claim being
# tested, not a description of the trace.
DENIED = [approve(1, "request"), approve(2, "error"), trade(3)]

SCENARIOS = [
    {
        "name": "response-gate, approval DENIED",
        "policy": POLICIES / "approval_gate_response.dw",
        "trace": DENIED,
        "why": "an error is not a response, so the gate must not open",
    },
    {
        "name": "request-gate, approval DENIED",
        "policy": POLICIES / "approval_gate_request.dw",
        "trace": DENIED,
        "why": "the attempt was recorded, so this weaker gate DOES open -- the finding",
    },
    {
        "name": "response-gate, approval ALLOWED",
        "policy": POLICIES / "approval_gate_response.dw",
        "trace": [approve(1, "request"), approve(2, "response"), trade(3)],
        "why": "the control: with a real response the same gate opens",
    },
    {
        "name": "response-gate, nothing at all",
        "policy": POLICIES / "approval_gate_response.dw",
        "trace": [trade(3)],
        "why": "deny by default on an empty history",
    },
    {
        "name": "error-gate, approval DENIED",
        "policy": POLICIES / "approval_gate_error.dw",
        "trace": DENIED,
        "why": "a policy can match error events directly, if it says so",
    },
    # Ordering on a DECIMAL. The guide says ordering "requires both sides to resolve to
    # integers; otherwise the comparison is false", and a decimal "resolves but fails the integer
    # conversion". Our model ordered decimals by their scaled value until 2026-09-11 -- a wrong
    # verdict, not a missing feature, and one no corpus case could catch: not one compares a
    # decimal with an ordering operator.
    {
        "name": "ordering on a Long output (control)",
        "policy": POLICIES / "order_long.dw",
        "trace": scored(1) + [trade(4)],
        "why": "the shape works: 7 > 0 on a Long output opens the gate",
    },
    {
        "name": "ordering on a DECIMAL output",
        "policy": POLICIES / "order_decimal.dw",
        "trace": scored(1) + [trade(4)],
        "why": "same shape, decimal column: ordering is not defined on one, so the gate stays shut",
    },
    # One policy, unchanged, under two shipped presets. The pin is the variable.
    {
        "name": "session gate, SAME session, session-pinned",
        "policy": POLICIES / "session_gate.dw",
        "trace": [approve(1, "request", "s1"), trade(3, session="s1")],
        "schema": "session-pinned.dwschema",
        "why": "the approval is in this session, so the pin admits it",
    },
    {
        "name": "session gate, OTHER session, session-pinned",
        "policy": POLICIES / "session_gate.dw",
        "trace": [approve(1, "request", "s2"), trade(3, session="s1")],
        "schema": "session-pinned.dwschema",
        "why": "same principal, same approval, different session -- the pin hides it",
    },
    {
        "name": "session gate, OTHER session, unpinned",
        "policy": POLICIES / "session_gate.dw",
        "trace": [approve(1, "request", "s2"), trade(3, session="s1")],
        "schema": "unpinned.dwschema",
        "why": "the control: without the pin the same trace permits, so the DENY above is the pin",
    },
]


def replay(policy_path: Path, trace_path: Path, schema: str | None = None) -> dict[int, bool]:
    """Ask the real engine. Returns {timestamp: allowed}.

    Without `--event-schema` the engine uses its built-in request/response/error shape, which is
    what every scenario but the session ones wants.
    """
    args = ["--event-schema", str(EVENT_SCHEMAS / schema)] if schema else []
    proc = subprocess.run(
        [str(DOGWOOD), "replay", "--policy-schema", str(SCHEMA), *args,
         "--trace", str(trace_path), str(policy_path)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"dogwood replay failed:\n{proc.stdout}{proc.stderr}")

    # Keyed on the `@N` timestamp, NOT on "time point". The CLI numbers time points
    # sequentially over decision events while the corpus fixtures index into the whole
    # trace, and mixing the two silently misaligns the verdicts.
    out = {}
    for m in re.finditer(r"@(\d+) \(time point \d+\): (ALLOW|DENY)", proc.stdout):
        out[int(m.group(1))] = m.group(2) == "ALLOW"
    if not out:
        raise RuntimeError(f"no verdicts parsed from:\n{proc.stdout}")
    return out


def model(policy_text: str, trace_lines: list[str], oracle: dict[int, bool],
          schema: str | None = None) -> tuple[bool, str]:
    """Ask our TLA+ semantics the same question, with the engine's answers as the oracle.

    Both halves of the schema matter and they are different things: `apply_pins` turns a PARTIAL
    pin into an ordinary conjunct, while `stamp_keys` records a UNIVERSAL pin as a partition key on
    every term. Omitting the second silently searches the whole trace -- which is exactly the bug
    these scenarios were written after finding.
    """
    policies = parse_policies(policy_text)
    sch = ({"keys": [], "partial": {}} if schema is None
           else parse_schema((EVENT_SCHEMAS / schema).read_text(encoding="utf-8")))
    apply_pins(policies, sch)
    if sch["keys"]:
        stamp_keys(policies, sch["keys"])

    events = parse_trace("\n".join(trace_lines), sch.get("paths"))

    times = [e["time"] for e in events]
    if len(times) != len(set(times)):
        raise Unsupported("two events share a timestamp, so verdicts cannot be aligned")

    indexed = {i + 1: oracle[e["time"]] for i, e in enumerate(events) if e["time"] in oracle}
    return check(generate_module([case_record("scenario", policies, events, indexed)]))


def main() -> int:
    if not DOGWOOD.exists():
        print(f"SKIPPED: no dogwood binary at {DOGWOOD.relative_to(REPO)}\n"
              "Build it with:\n"
              "  cargo build --release --locked "
              "--manifest-path ext/dogwood/Cargo.toml", file=sys.stderr)
        return 2

    print(f"{len(SCENARIOS)} scenarios, none of which the recorded corpus covers\n")
    failures = 0

    with tempfile.TemporaryDirectory(prefix="anchor-replay-") as tmp:
        trc = Path(tmp) / "t.log"
        for s in SCENARIOS:
            if not s["policy"].exists():
                raise FileNotFoundError(s["policy"])
            trc.write_text("\n".join(s["trace"]) + "\n", encoding="utf-8")

            oracle = replay(s["policy"], trc, s.get("schema"))
            agreed, output = model(s["policy"].read_text(encoding="utf-8"), s["trace"], oracle,
                                   s.get("schema"))

            verdicts = ", ".join(f"@{t}={'ALLOW' if v else 'DENY'}" for t, v in sorted(oracle.items()))
            mark = "" if agreed else "   ! MODEL DISAGREES"
            failures += not agreed
            print(f"  {s['name']:43} {verdicts:<28}{mark}")
            print(f"  {'':43} {s['why']}")
            if not agreed:
                for line in output.splitlines():
                    if "DISAGREEMENT" in line:
                        print(f"  {'':43} {line.strip()}")
            print()

    if failures:
        print(f"{failures} scenario(s) where our semantics and the engine disagree")
        return 1

    print("our semantics agrees with the Dogwood engine on every scenario -- both blind spots\n"
          "the recorded corpus has: the `error` event kind, which appears in none of its 521\n"
          "cases, and the shipped `session-pinned` event schema, whose pin shape appears in none\n"
          "of them either. The last two scenarios are the same policy and the same trace under\n"
          "two shipped presets, deciding differently.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
