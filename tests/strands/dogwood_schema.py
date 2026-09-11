"""Reading an `event.dwschema`, for the one thing in it that changes what a policy MEANS: pins.

A pin declares that a field of every event is implicitly forced to equal something about the
decision. The policy never writes it, cannot see it, and cannot bypass it:

    decision event <A>::request {
        ...inputs(A),
        pin callerPrincipal: principalType(A) = principal,
        ...
    }

That is the finding this module exists for. **A policy's meaning is not determined by its own
text** — read the `.dw` and ignore the schema and you get a different answer than the engine does.
It is also what caught our translator the first time the corpus ran.

UNIVERSAL VERSUS PARTIAL, which is the subtle half. A pin declared on EVERY event kind is
universal and switches the leaf to key-local semantics: the trace is partitioned by the pinned key
and temporal operators see only your own partition. A pin declared on some kinds but not others is
partial, earns no isolation, and stays global — the corpus's own words: "the engine must not grant
isolation the schema did not earn."

The difference is invisible to `formerly`, `count` and `sum`, which are existential — restricting
the candidates is the same as adding a conjunct. It is visible to `previous`, which means *the most
recent match*: globally a foreign event can BE the most recent one and fail the predicate, where
partitioned it is skipped entirely. `1155_relativize_previous_ignores_foreign` and
`1164_partial_pin_stays_global` are the same policy and the same trace with opposite verdicts, and
the only difference between them is whether the pin covers both kinds.

THE MODELLED SUBSET is universal and partial pins on the two SCOPE fields, `callerPrincipal` and
`callerResource`. Everything else here is refused rather than guessed at:

    - nested pins (`__drupe: { pin session_id: ... }`), which pin a path rather than a field
    - pins on a context field (`pin tenant_id: String = context.tenant_id`)
    - schemas with custom event kinds (`attempt`/`outcome` rather than request/response)
    - schemas with no pin at all, which are in the corpus for other features entirely --
      renamed reserved fields, deep paths, injected slots
"""

from __future__ import annotations

import re

from dogwood_parse import Unsupported

# `pin <field>: <type> = <source>` at the top level of an event block.
PIN = re.compile(r"^\s*pin\s+([A-Za-z_]\w*)\s*:\s*[^=]+=\s*([A-Za-z_][\w.]*)\s*,?\s*$", re.M)

# A nested block that contains a pin -- `__drupe: { pin session_id: ... }`. Detected only so it
# can be refused by name rather than silently missed.
NESTED_PIN = re.compile(r"([A-Za-z_]\w*)\s*:\s*\{[^}]*\bpin\b", re.S)

EVENT = re.compile(r"^\s*(decision\s+)?event\s+<A>::([A-Za-z_]\w*)\s*\{", re.M)

CONVENTIONAL = {"request", "response", "error"}

# The scope fields, and the key each one partitions on.
SCOPE_PINS = {"callerPrincipal": "principal", "callerResource": "resource"}


def _block(text: str, start: int) -> str:
    """The braced block beginning at `start` (just past its opening brace)."""
    depth, j = 1, start
    while j < len(text) and depth:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
        j += 1
    return text[start:j]


def parse_schema(text: str) -> dict:
    """`{"keys": [...], "partial": {kind: [bind, ...]}}` for a schema inside the subset.

    `keys` are the partition keys a universal pin establishes -- empty when there is none, which
    is the same as having no schema at all. `partial` gives the binds to inject per event kind.
    """
    text = re.sub(r"//[^\n]*", "", text)

    if NESTED_PIN.search(text):
        name = NESTED_PIN.search(text).group(1)
        raise Unsupported(f"schema pins a nested path ({name}.*), not a top-level field")

    kinds, pins = [], {}
    for m in EVENT.finditer(text):
        kind = m.group(2)
        kinds.append(kind)
        pins[kind] = dict(PIN.findall(_block(text, m.end())))

    if not kinds:
        raise Unsupported("event schema declares no event kinds")

    unknown = set(kinds) - CONVENTIONAL
    if unknown:
        raise Unsupported(f"schema declares custom event kinds: {', '.join(sorted(unknown))}")

    declared = set().union(*pins.values()) if pins else set()
    if not declared:
        # The other ten schema cases -- renamed slots, deep paths, injected fields. Each is a
        # separate feature, and none of them is this one.
        raise Unsupported("event schema declares no pin (it is in the corpus for another feature)")

    outside = declared - set(SCOPE_PINS)
    if outside:
        raise Unsupported(f"schema pins a non-scope field: {', '.join(sorted(outside))}")

    for kind, declared_here in pins.items():
        for field, source in declared_here.items():
            if source != SCOPE_PINS[field]:
                raise Unsupported(f"pin {field} = {source}, not the matching scope field")

    universal = [f for f in sorted(declared) if all(f in pins[k] for k in kinds)]
    partial = sorted(declared - set(universal))

    return {
        "keys": [SCOPE_PINS[f] for f in universal],
        # A partial pin earns no partition, so it acts as an ordinary conjunct on the kinds that
        # declare it -- and on those only.
        "partial": {kind: [_bind(f) for f in sorted(partial) if f in pins[kind]]
                    for kind in kinds},
    }


def _bind(field: str) -> dict:
    """The bind a pin injects -- the same record the parser builds for a written one."""
    return {"side": "scope", "field": field, "kind": "scope",
            "name": SCOPE_PINS[field], "value": ""}


def apply_pins(policies: list[dict], schema: dict) -> None:
    """Inject each partial pin's bind into the predicates of the kind that declares it.

    In place, and only for PARTIAL pins. A universal pin needs no conjunct: partitioning already
    restricts every candidate to events that agree on the key, so writing it in as well would be
    the same condition twice.
    """
    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        if pred := node.get("pred"):
            for b in schema["partial"].get(pred.get("kind"), []):
                if not any(x["field"] == b["field"] and x["side"] == "scope"
                           for x in pred["binds"]):
                    pred["binds"].append(b)
        for key in ("term", "atom", "left", "cond", "agg"):
            walk(node.get(key))
        for child in node.get("args", []) or []:
            walk(child)

    for p in policies:
        walk(p["cond"])
