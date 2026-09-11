"""Read a Dogwood event trace into the records the TLA+ semantics evaluates.

A `trace.log` line is an event: an action, a kind, input and output records, and the scope envelope
carrying principal, resource and session. The reader is deliberately intolerant -- a field it
cannot represent raises `Unsupported` rather than being dropped, because a trace quietly missing a
field makes every verdict computed from it meaningless in a way no test would catch.

`@N` is SECONDS, fixed by corpus case 0127: a read 12s after a login is denied under a `within 10s`
window and one 8s after is allowed.
"""

from __future__ import annotations

import re

from .parse import UNITS, Dec, Unsupported, parse_decimal

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
