"""Dogwood policy text in, TLA+ policy data out.

This is the translator the specs, the harnesses and (shortly) the MCP server all read a policy
through. It exists as a package because it was previously scattered: the parser and the schema
reader sat in `tests/strands/` beside the harnesses that exercised them, and every TLA+ emitter
lived *inside* `dogwood_differential.py` -- so `dw_to_tla.py`, which translates policies for a
checked-in spec, imported `tla_cond` from a test harness. Two symptoms made the missing layer
obvious: `UNITS` and `policy_seq` were each defined twice, character for character.

    .dw text ──> parse ──> policy dicts ──> emit ──> TLA+ records ──> tlc ──> a verdict
                   ▲                                        ▲
             schema (pins)                          trace (events)

WHAT IS AND IS NOT IN HERE. The library translates and runs; it does not decide what to check. The
differential harnesses, the corpus walkers and the vacuity CLI are consumers and stay in their own
projects. The test for whether something belongs here is whether the MCP server would need it to
answer a question about a policy it was handed.

Nothing imports from `tests/`. If that ever reverses again, this file is the place it will show.
"""

from __future__ import annotations

from .emit import (DUMMY_ATOM, DUMMY_PRED, DUMMY_TERM, NO_CMP, policy_seq, stamp_keys, tla_atom,
                   tla_cond, tla_pattern, tla_pred, tla_record, tla_scalar, tla_value)
from .policy_module import (DECISION_KIND, KINDS, field_domain, generate_policy_module,
                            joint_witness, vocabulary)
from .parse import (DECIMAL_SCALE, DEFAULT_MAX_WINDOW, UNITS, WILDCARD, Dec, Parser,
                    Unsupported, collect_macros,
                    expand_macros, like_matches, parse_cidr, parse_decimal, parse_like_pattern,
                    parse_policies, pattern_witnesses, tokenize)
from .schema import SCOPE_PINS, apply_pins, key_for, parse_schema
from .tlc import (TLAParseError, attempts_of, find_jar, narrate, parse_tla_value, run_eval, run_sany,
                  render_fields, render_value, run_tlc, trace_states, untag, witness_events)
from .trace import braced, parse_fields, parse_trace, pin_value, split_binds

__all__ = [
    # parse
    "DECIMAL_SCALE", "DEFAULT_MAX_WINDOW", "Dec", "Parser", "UNITS", "Unsupported",
    "WILDCARD", "collect_macros",
    "expand_macros", "like_matches", "parse_cidr", "parse_decimal", "parse_like_pattern",
    "parse_policies",
    "pattern_witnesses", "tokenize",
    # schema
    "SCOPE_PINS", "apply_pins", "key_for", "parse_schema",
    # the seam every check extends
    "DECISION_KIND", "KINDS", "field_domain", "generate_policy_module", "joint_witness",
    "vocabulary",
    # trace
    "braced", "parse_fields", "parse_trace", "pin_value", "split_binds",
    # emit
    "DUMMY_ATOM", "DUMMY_PRED", "DUMMY_TERM", "NO_CMP", "policy_seq", "stamp_keys", "tla_atom",
    "tla_cond", "tla_pattern", "tla_pred", "tla_record", "tla_scalar", "tla_value",
    # tlc
    "find_jar", "run_tlc", "run_sany", "run_eval", "trace_states", "witness_events", "parse_tla_value", "untag",
    "narrate", "attempts_of", "render_value", "render_fields",
    "TLAParseError",
]
