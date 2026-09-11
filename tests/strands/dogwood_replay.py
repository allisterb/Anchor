"""Differential test against the Dogwood engine itself, on traces we construct.

`dogwood_differential.py` checks our semantics against the reference corpus. That validates a lot —
732 pairs — but only over traces Amazon happened to record, and the corpus has a blind spot we care
about: across all 521 cases, `::error` appears in **zero** policies and **zero** traces.

That matters because the `error` event kind is exactly what `specs/policy/TemporalPolicy`'s findings rest
on. AgentCore records a denied action as an `error` rather than a `response`, which is why a permit
gated on `::response` goes vacuous when the action it depends on is forbidden, and why the same rule
written against `::request` does not. Until now that was documented and modelled but never executed.

The built `dogwood` binary closes it. Unlike the corpus it is a live oracle: it will judge any trace
we hand it, including ones with event kinds the corpus never uses.

    approval_gate_*.dw ──┬── dogwood replay ──────────────────────> verdicts (the oracle)
                         └── dogwood_parse ──> TLA+ data ──> TLC ──> our verdicts

Both sides read the same policy file, so a disagreement is ours. The three gates differ by exactly
one word -- `response`, `request`, `error` -- which is the point being made.

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

from dogwood_differential import case_record, check, generate_module, parse_trace  # noqa: E402
from dogwood_parse import Unsupported, parse_policies  # noqa: E402

SCOPE = 'scope(principal: Anchor::OAuthUser::"alice", resource: Anchor::Gateway::"gw1")'
CALLER = 'callerPrincipal: Anchor::OAuthUser::"alice", callerResource: Anchor::Gateway::"gw1"'


def approve(t: int, kind: str) -> str:
    ctx = 'request_context(input: { approver: "alice" }) ' if kind == "request" else ""
    return (f'@{t} {SCOPE} {ctx}Anchor::Action::"Approve"::{kind}'
            f'(input: {{ approver: "alice" }}, {CALLER}, requestId: "a{t}")')


def trade(t: int, amount: int = 1) -> str:
    return (f'@{t} {SCOPE} request_context(input: {{ amount: {amount} }}) '
            f'Anchor::Action::"Trade"::request(input: {{ amount: {amount} }}, '
            f'{CALLER}, requestId: "t{t}")')


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
]


def replay(policy_path: Path, trace_path: Path) -> dict[int, bool]:
    """Ask the real engine. Returns {timestamp: allowed}."""
    proc = subprocess.run(
        [str(DOGWOOD), "replay", "--policy-schema", str(SCHEMA),
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


def model(policy_text: str, trace_lines: list[str], oracle: dict[int, bool]) -> tuple[bool, str]:
    """Ask our TLA+ semantics the same question, with the engine's answers as the oracle."""
    policies = parse_policies(policy_text)
    events = parse_trace("\n".join(trace_lines))

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

            oracle = replay(s["policy"], trc)
            agreed, output = model(s["policy"].read_text(encoding="utf-8"), s["trace"], oracle)

            verdicts = ", ".join(f"@{t}={'ALLOW' if v else 'DENY'}" for t, v in sorted(oracle.items()))
            mark = "" if agreed else "   ! MODEL DISAGREES"
            failures += not agreed
            print(f"  {s['name']:36} {verdicts:<28}{mark}")
            print(f"  {'':36} {s['why']}")
            if not agreed:
                for line in output.splitlines():
                    if "DISAGREEMENT" in line:
                        print(f"  {'':36} {line.strip()}")
            print()

    if failures:
        print(f"{failures} scenario(s) where our semantics and the engine disagree")
        return 1

    print("our semantics agrees with the Dogwood engine on every scenario, including the\n"
          "`error` event kind that appears nowhere in the reference corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
