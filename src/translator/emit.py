"""Emit the TLA+ data that `DogwoodSemantics` evaluates.

Every value is TAGGED with its kind -- `[k |-> "s", v |-> "AMZN"]` -- so TLC refuses a comparison
across kinds rather than quietly answering one. A Cedar decimal and a Long that happen to share a
scaled value are different values and must never compare equal.

Atom records are kept UNIFORM: every atom carries the same field set, `NO_CMP` filling the ones a
given op does not use. Differing shapes would also work, but uniformity means a new op cannot
silently omit a field that an evaluator later reads.
"""

from __future__ import annotations

from .parse import WILDCARD, Dec, Unsupported

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


def policy_seq(policies: list[dict], indent: str = "    ") -> str:
    """A policy list as the TLA+ sequence `Decide` walks.

    This lived in two places -- `dw_to_tla` and `vacuity` -- character for character, which is what
    a missing library layer looks like from the outside.
    """
    return ",\n".join(
        f'{indent}[effect |-> "{p["effect"]}", action |-> "{p["action"]}", '
        f'cond |-> {tla_cond(p["cond"])}]'
        for p in policies)
