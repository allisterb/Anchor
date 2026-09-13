"""Turn a counterexample back into the user's own language, and ask the reference engine.

    python src/checker/witness.py examples/aws1/07-trust-decay.dw --property examples/aws1/TrustDecay.tla

A broken property currently ends the conversation with a TLA+ state:

    BROKEN  Invariant LosesWriteAfter15m is violated by the initial state:
        gap = 960

Which is correct, and is the answer in the wrong language. The input to all of this was a `.dw`
file the author wrote and can read; the output is a variable belonging to a TLA+ module that a
tool drafted, holding a number whose units are not written down. Somebody who knows Dogwood and
not TLA+ -- which is the person the policy belongs to -- cannot check that finding, and a finding
nobody can check is a finding nobody acts on.

So this closes the loop, in two steps that are worth keeping separate:

    1. WHAT SESSION IS THAT?   `gap = 960` means nothing alone, but the property module says
                               exactly what it means: `Session(gap) == << Interaction(1),
                               Trade(1 + gap) >>`. That recipe is in the module, it is already
                               parsed, and evaluating it at 960 gives concrete events with times.

    2. ASK DOGWOOD.            Those events render as a Dogwood `.log` trace, and `dogwood replay`
                               judges it. The verdict comes from Amazon's own engine, on the
                               author's own policy file, at a stated time -- not from our model.

THE SECOND STEP IS THE POINT, and it is a different KIND of evidence from everything else here.
Every other verdict in this project rests on our TLA+ semantics being a faithful reading of
Dogwood, which is established by differential testing and is therefore a very good argument rather
than a proof. A replay is not an argument at all: it is the reference implementation answering the
question directly. When the two agree, the finding no longer depends on us being right about
Dogwood.

And when they DISAGREE that is a bug in Anchor, reported as one. A disagreement here is the most
valuable output this file can produce, so it is never quietly dropped.

    .dw + .tla ──> TLC ──> `gap = 960` ──> Session(960) ──> events ──> .log ──┐
         │                                                                     ├──> dogwood replay
         └─────────────────────────────────────────────────────────────────────┘         │
                                                                                      ALLOW/DENY
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from checker.explain import (Module, Rec, Seq, Tag, Unknown, parse,  # noqa: E402
                             read, show_value)
from translator import parse_tla_value  # noqa: E402

# The built binary, which is not in the repo. Absent is not an error: everything up to the replay
# still works and is still worth printing, so a missing binary costs the confirmation and nothing
# else. Built with:
#     cargo build --release --locked --manifest-path ext/dogwood/Cargo.toml
DOGWOOD = (REPO / "ext" / "dogwood" / "target" / "release"
           / ("dogwood.exe" if sys.platform == "win32" else "dogwood"))

# A state conjunct as TLC prints it, and the invariant line above it.
VIOLATION = re.compile(r"Invariant (\w+) is violated")
BINDING = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*) = (.+)$")

# `AgentCore::Action::"execute_trade"` -- the namespace the policy writes its actions in. The
# parser drops it (Anchor models actions and kinds, not entity hierarchies) and a replay needs it
# back, because the trace and the schema must both use the policy's own.
NAMESPACE = re.compile(r'(\w+)::Action::"')

# Cedar types for the tagging discipline's four kinds. An address has no Dogwood scalar form we
# model, so a witness carrying one is refused rather than rendered wrongly -- see `scalar`.
CEDAR_TYPES = {"n": "Long", "s": "String", "b": "Bool"}


# ---------------------------------------------------------------------------- the counterexample
@dataclass
class Violation:
    """One invariant TLC reported false, and the state it was false in."""

    invariant: str
    state: dict[str, Any]                          # variable -> value, in explain.py's value model
    printed: dict[str, str]                        # variable -> exactly what TLC printed


def retag(v: Any) -> Any:
    """A value parsed from TLC's output, in the value model `explain` evaluates with.

    The generated module tags every scalar -- `Num(22)` is the record `[k |-> "n", v |-> 22]` --
    so TLC prints the tag rather than the value. Converting here rather than at every use keeps
    one representation in play: whatever the module's own text evaluates to.
    """
    if isinstance(v, dict):
        if set(v) == {"k", "v"}:
            return Tag({"n": "Num", "s": "Str", "b": "Bool", "a": "Addr"}.get(v["k"], v["k"]),
                       retag(v["v"]))
        return Rec(tuple((k, retag(x)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return Seq(tuple(retag(x) for x in v))
    return v


def violations(out: str) -> list[Violation]:
    """Every counterexample in a TLC run, structured.

    TWO SHAPES, because TLC prints a multi-variable state as `/\\ name = value` conjuncts and a
    single-variable one as a bare `name = value`. A reader that handled only the first found
    nothing at all for the commonest property module, which holds exactly one variable still.
    """
    lines, found = out.splitlines(), []
    for i, line in enumerate(lines):
        if not (m := VIOLATION.search(line)):
            continue

        state, printed = {}, {}
        for raw in lines[i + 1:i + 40]:
            s = raw.strip()
            if not s:
                break
            if not (b := BINDING.match(s.removeprefix("/\\").strip())):
                continue
            printed[b.group(1)] = b.group(2)
            try:
                state[b.group(1)] = retag(parse_tla_value(b.group(2))[0])
            except Exception:
                pass                                # printed but unreadable; recorded as text only
        found.append(Violation(m.group(1), state, printed))
    return found


# ---------------------------------------------------------------------------- what was demanded
@dataclass
class Demand:
    """The decision the violated claim is about, and what it required of it."""

    operator: str                                   # e.g. `TradeAllowed`
    allow: bool                                     # what the property demanded the policy do
    events: list[Rec] = field(default_factory=list)  # the session, concrete
    index: int = 0                                  # which event of it is being decided, from 1
    why: str = ""                                   # why the above is empty, when it is


def decisions(module: Module, tree) -> list[str]:
    """Operators in this expression that ask the policy for a decision, outermost first."""
    out: list[str] = []

    def walk(node):
        match node:
            case ("app", name, args):
                d = module.defs.get(name)
                if d and "Decide" in d.source and name not in out:
                    out.append(name)
                for a in args:
                    walk(a)
            case ("bin", _, l, r):
                walk(l)
                walk(r)
            case ("un", _, x) | ("quant", _, _, x):
                walk(x)
    walk(tree)
    return out


def decide_call(module: Module, operator: str):
    """The `D!Decide(trace, Policies, index, values)` inside `operator`, as (trace, index)."""
    d = module.defs.get(operator)
    if d is None or (tree := d.tree()) is None:
        return None

    found = []

    def walk(node):
        match node:
            case ("app", name, args):
                if name.split("!")[-1] == "Decide" and len(args) >= 3:
                    found.append((args[0], args[2]))
                for a in args:
                    walk(a)
            case ("bin", _, l, r):
                walk(l)
                walk(r)
            case ("un", _, x):
                walk(x)
    walk(tree)
    return (d.params, *found[0]) if found else None


def demanded(module: Module, invariant: str, violation: Violation) -> Demand | None:
    """What the property required the policy to decide, in the state that broke it.

    NOT READ OFF THE SYNTAX. A claim can put the decision in either half of an implication and
    under any number of negations -- `Allowed(p) => (p = "both")` is violated by an ALLOW, while
    `(gap > 900) => ~Allowed(gap)` is violated by an ALLOW too, and `(gap <= 900) => Allowed(gap)`
    by a DENY. Rather than enumerate those, the claim is evaluated twice with the decision assumed
    each way: the assumption that makes it FALSE is what the policy must have done, and the other
    is what the property demanded.

    That also CHECKS THIS READER against TLC. If neither assumption makes the claim false, then
    this module and TLC disagree about what a counterexample is, and the honest thing is to say so
    and claim nothing.
    """
    d = module.defs.get(invariant)
    if d is None or (tree := d.tree()) is None:
        return None

    names = decisions(module, tree)
    if not names:
        return Demand("", False, why="the claim asks the policy for no decision, so there is "
                                     "nothing to replay")
    if len(names) > 1:
        return Demand(names[0], False,
                      why=f"the claim combines {len(names)} decisions ({', '.join(names)}); "
                          f"which one the counterexample is about is not decidable from it alone")

    operator = names[0]
    breaks = [assumed for assumed in (True, False)
              if module.assuming(operator, assumed).evaluate(tree, violation.state) is False]

    if len(breaks) != 1:
        return Demand(operator, False,
                      why=("this reader could not reproduce TLC's counterexample, so it will not "
                           "say what the claim demanded. TLC is right and this is a defect here"
                           if not breaks else
                           "the claim is false in this state whatever the policy decides, so it "
                           "demands nothing of the policy"))

    return Demand(operator, allow=not breaks[0])


def session(module: Module, demand: Demand, violation: Violation) -> Demand:
    """Fill in the concrete session the demand is about, from the module's own recipe."""
    call = decide_call(module, demand.operator)
    if call is None:
        demand.why = f"{demand.operator} does not call Decide in a shape this reader recognises"
        return demand

    params, trace_expr, index_expr = call

    # The decision operator takes the state variable as its argument -- `TradeAllowed(gap)` -- so
    # its parameter has to be bound to the counterexample's value before its body means anything.
    # Bound positionally from the call site rather than by name: the parameter is usually named
    # after the variable and must not be assumed to be.
    env = dict(violation.state)
    if len(params) == 1 and len(violation.state) == 1:
        env[params[0]] = next(iter(violation.state.values()))
    elif params:
        for p in params:
            if p in violation.state:
                env[p] = violation.state[p]

    events = module.evaluate(trace_expr, env)
    index = module.evaluate(index_expr, env)

    if not isinstance(events, Seq) or not all(isinstance(e, Rec) for e in events.items):
        demand.why = (f"the session `{demand.operator}` decides could not be worked out from the "
                      f"module -- it is built with something this reader does not evaluate")
        return demand
    if not isinstance(index, int) or isinstance(index, bool):
        demand.why = "which event of the session is decided could not be worked out"
        return demand

    demand.events = list(events.items)
    demand.index = index
    return demand


# ---------------------------------------------------------------------------- Dogwood's language
def namespace_of(policy_text: str) -> str:
    """The namespace the policy writes its actions in, or Anchor's own if it names none.

    The parser drops it -- Anchor models actions and event kinds rather than entity hierarchies --
    and a replay needs it back, because the trace and the generated schema must both agree with
    the policy about what `Action::"execute_trade"` is called.
    """
    return m.group(1) if (m := NAMESPACE.search(policy_text)) else "Anchor"


def scalar(v: Any) -> str:
    """A tagged value as Dogwood writes it. Raises rather than guess."""
    if isinstance(v, Tag):
        if v.kind == "Num":
            return str(v.value)
        if v.kind == "Str":
            return f'"{v.value}"'
        if v.kind == "Bool":
            return "true" if v.value else "false"
        raise Unsupported(f"{v.kind} has no scalar form this renderer writes")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    raise Unsupported(f"{show_value(v)} has no scalar form this renderer writes")


class Unsupported(Exception):
    """Something the renderer will not guess at. Always reported, never approximated."""


def fields(rec: Any) -> str:
    if not isinstance(rec, Rec) or not rec.fields:
        return " "
    return " " + ", ".join(f"{k}: {scalar(v)}" for k, v in rec.fields) + " "


def trace_text(events: list[Rec], namespace: str, decision_kind: str = "request") -> str:
    """The session as a Dogwood `.log` trace.

    The principal and resource are constants: the property modules build sessions with the
    generated module's `Anon`, so a witness says nothing about who the caller was and inventing a
    difference between events would be inventing a fact. One caller, one gateway.
    """
    scope = (f'scope(principal: {namespace}::OAuthUser::"agent", '
             f'resource: {namespace}::Gateway::"gw")')
    caller = (f'callerPrincipal: {namespace}::OAuthUser::"agent", '
              f'callerResource: {namespace}::Gateway::"gw"')

    lines = []
    for n, e in enumerate(events, 1):
        action, kind = e.get("action"), e.get("kind")
        if not isinstance(action, str) or not isinstance(kind, str):
            raise Unsupported("an event's action or kind is not a plain string")

        # `request_context` carries what the decision is being asked ABOUT, and only a decision
        # event has one. An output only exists on a response.
        context = f"request_context(input: {{{fields(e.get('input'))}}}) " if kind == decision_kind else ""
        output = (f"output: {{{fields(e.get('output'))}}}, "
                  if kind == "response" else "")
        lines.append(f'@{e.get("time")} {scope} {context}{namespace}::Action::"{action}"::{kind}'
                     f'(input: {{{fields(e.get("input"))}}}, {output}{caller}, requestId: "e{n}")')
    return "\n".join(lines) + "\n"


def cedar_schema(vocab: dict, namespace: str, events: list[Rec]) -> str:
    """A Cedar schema for this policy's actions, generated rather than written.

    `dogwood replay` requires one, and hand-writing it per example would be a second description
    of the policy to keep in step with the first. The actions and the field names come from the
    policy's own text, via the same vocabulary the TLA+ module is generated from; the field TYPES
    come from the literals it compares against.
    """
    def typed(side: str) -> list[str]:
        names = set(vocab.get(side, set()))
        for e in events:                            # plus anything the witness itself carries
            rec = e.get(side)
            if isinstance(rec, Rec):
                names.update(k for k, _ in rec.fields)

        out = []
        for name in sorted(names):
            domain = vocab.get("domains", {}).get((side, name)) or []
            kinds = {k for k, _ in domain} or {"s"}
            # All optional: not every event carries every field, and a required one the witness
            # omits is a schema error rather than a verdict.
            out.append(f"    {name}?: {CEDAR_TYPES.get(next(iter(kinds)), 'String')}")
        return out

    def record(name: str, side: str) -> str:
        body = typed(side)
        return f"  type {name} = {{\n" + ",\n".join(body) + "\n  };" if body else \
               f"  type {name} = {{}};"

    actions = "\n".join(
        f'  action "{a}" in [Action::"CallTool"] appliesTo {{\n'
        f"    principal: [OAuthUser], resource: [Gateway],\n"
        f"    context: {{ input: EventInput, output?: EventOutput, system: SystemContext }}\n"
        f"  }};"
        for a in sorted(vocab.get("actions", ())))

    return (f"// Generated by Anchor from the policy's own vocabulary, for `dogwood replay`.\n"
            f"// Every field is optional: a witness names only the fields its claim is about.\n"
            f"namespace {namespace} {{\n"
            f"  type SystemContext = {{ now: datetime }};\n"
            f"{record('EventInput', 'input')}\n"
            f"{record('EventOutput', 'output')}\n\n"
            f"  entity Gateway;\n"
            f"  entity OAuthUser = {{ id: String }} tags String;\n\n"
            f'  action "CallTool";\n\n'
            f"{actions}\n"
            f"}}\n")


def replay(policy: Path, trace: Path, schema: Path, dogwood: Path = DOGWOOD) -> dict:
    """Ask the engine. Returns {timestamp: "allow"/"deny"} plus whatever it said."""
    proc = subprocess.run(
        [str(dogwood), "replay", "--format", "json", "--policy-schema", str(schema),
         "--trace", str(trace), str(policy)],
        capture_output=True, text=True, timeout=120)

    if proc.returncode != 0:
        return {"_failed": True, "_why": (proc.stdout + proc.stderr).strip()[-1200:]}
    try:
        # Keyed on the `@N` TIMESTAMP, never on the index. The CLI numbers time points
        # sequentially over decision events while a trace numbers every event, and mixing the two
        # silently misaligns verdicts -- a wrong answer that looks like a right one.
        return {v["timestamp"]: v["verdict"] for v in json.loads(proc.stdout)["verdicts"]}
    except (json.JSONDecodeError, KeyError) as e:
        return {"_failed": True, "_why": f"could not read the engine's reply ({e}):\n{proc.stdout[-800:]}"}


# ---------------------------------------------------------------------------- putting it together
@dataclass
class Confirmation:
    """One counterexample, in Dogwood's terms, with the engine's verdict on it."""

    invariant: str
    state: dict[str, str]
    operator: str = ""
    demanded: bool | None = None                    # what the property required: allow / refuse
    engine: str | None = None                       # what the engine did: "allow" / "deny"
    agreed: bool | None = None                      # does the engine confirm the finding?
    at: int | None = None                           # the timestamp it judged
    events: list[dict] = field(default_factory=list)
    trace: str = ""
    schema: str = ""
    why: str = ""                                   # why there is no verdict, when there is none

    def sentence(self) -> str:
        """The finding, in one line, for somebody who reads `.dw` and not TLA+."""
        if self.demanded is None:
            return self.why or "no verdict"

        want = "REFUSE" if not self.demanded else "ALLOW"
        where = ", ".join(f"{k} = {v}" for k, v in self.state.items())
        if self.engine is None:
            return (f"your policy must {want} the session below ({where}), and the model says it "
                    f"does not. {self.why}".strip())

        did = "ALLOWS" if self.engine == "allow" else "REFUSES"
        if self.agreed:
            return (f"with {where}, the Dogwood engine {did} this session at t={self.at}, where "
                    f"`{self.invariant}` says your policy must {want} it")
        return (f"the Dogwood engine does {want} this session at t={self.at}, which is what "
                f"`{self.invariant}` asked for, so our model and the engine disagree about this "
                f"policy. That is a defect in Anchor, not a finding about your policy")


def confirm(policy: Path, module: Path, tlc_output: str, *,
            dogwood: Path = DOGWOOD, keep: Path | None = None) -> list[Confirmation]:
    """Every counterexample in `tlc_output`, replayed against the real engine where possible."""
    from translator import DEFAULT_MAX_WINDOW, parse_policies, vocabulary   # noqa: PLC0415

    text = policy.read_text(encoding="utf-8")
    namespace = namespace_of(text)
    policies = parse_policies(text, "", DEFAULT_MAX_WINDOW)
    vocab = vocabulary(policies, 2, 8)

    spec = read(module)
    out: list[Confirmation] = []

    for v in violations(tlc_output):
        c = Confirmation(invariant=v.invariant, state=dict(v.printed))
        out.append(c)

        d = demanded(spec, v.invariant, v)
        if d is None:
            c.why = f"{v.invariant} is not defined in {module.name}"
            continue

        c.operator, c.demanded = d.operator, (d.allow if not d.why else None)
        if d.why:
            c.why = d.why
            continue

        d = session(spec, d, v)
        if d.why:
            c.why = d.why
            continue

        try:
            c.trace = trace_text(d.events, namespace)
            c.schema = cedar_schema(vocab, namespace, d.events)
        except Unsupported as e:
            c.why = f"this witness cannot be written as a Dogwood trace: {e}"
            continue

        # Action, kind and time stay as values; input and output are rendered, because they
        # are records and a reader wants them the way the policy writes them.
        c.events = [{"time": e.get("time"), "action": e.get("action"), "kind": e.get("kind"),
                     "input": show_value(e.get("input")),
                     "output": show_value(e.get("output"))} for e in d.events]
        decided = d.events[d.index - 1] if 0 < d.index <= len(d.events) else d.events[-1]
        c.at = decided.get("time") if isinstance(decided.get("time"), int) else None

        if not dogwood.exists():
            c.why = (f"no dogwood binary at {dogwood.relative_to(REPO) if dogwood.is_relative_to(REPO) else dogwood}"
                     f" -- build it to have the engine confirm this")
            continue

        with tempfile.TemporaryDirectory(prefix="anchor-witness-") as tmp:
            work = Path(keep) if keep else Path(tmp)
            work.mkdir(parents=True, exist_ok=True)
            (trace := work / f"{v.invariant}.log").write_text(c.trace, encoding="utf-8")
            (schema := work / "generated.cedarschema").write_text(c.schema, encoding="utf-8")

            verdicts = replay(policy, trace, schema, dogwood)

        if verdicts.get("_failed"):
            c.why = f"the engine could not replay this: {verdicts['_why']}"
            continue

        c.engine = verdicts.get(c.at) or next(iter(verdicts.values()), None)
        if c.engine is None:
            c.why = "the engine returned no verdict for the decided event"
            continue
        # The property demanded `allow`; the engine did `allow` -> the engine does NOT confirm the
        # finding, and our model and the engine disagree.
        c.agreed = (c.engine == "allow") != d.allow

    return out


def render(confirmations: list[Confirmation]) -> str:
    lines: list[str] = []
    for c in confirmations:
        lines.append(f"  {c.invariant}")
        for k, v in c.state.items():
            lines.append(f"      TLC found      {k} = {v}")
        if c.events:
            lines.append("      which is       " + "  ".join(
                f'@{e["time"]} {e["action"]}::{e["kind"]}' for e in c.events))
        if c.engine:
            lines.append(f"      dogwood says   {c.engine.upper()} at t={c.at}"
                         + ("  -- confirms the finding" if c.agreed
                            else "  -- DISAGREES with our model"))
        lines.append(f"      so             {c.sentence()}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("policy", type=Path)
    ap.add_argument("--property", dest="module", type=Path, required=True)
    ap.add_argument("--keep", type=Path, default=None,
                    help="write the generated trace and schema here instead of discarding them")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    checker = REPO / "src" / "checker" / "properties.py"
    proc = subprocess.run([sys.executable, str(checker), str(args.policy),
                           "--property", str(args.module)],
                          cwd=REPO, capture_output=True, text=True, timeout=3600)
    found = confirm(args.policy, args.module, proc.stdout + proc.stderr, keep=args.keep)

    if args.json:
        print(json.dumps([{
            "invariant": c.invariant, "state": c.state, "demanded": c.demanded,
            "engine": c.engine, "confirms": c.agreed, "at": c.at, "events": c.events,
            "why": c.why, "sentence": c.sentence(),
        } for c in found], indent=2))
        return 0

    if not found:
        print("no counterexample -- every claim held.")
        return 0

    print(f"{args.policy.name} against {args.module.name}: "
          f"{len(found)} counterexample(s)\n")
    print(render(found))
    return 1 if any(c.agreed for c in found) else 0


if __name__ == "__main__":
    sys.exit(main())
