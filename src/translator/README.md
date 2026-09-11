# `translator` — Dogwood policy text to TLA+

Policy text in, the records `DogwoodSemantics!Decide` evaluates out. This is the one place a `.dw`
file is read, and everything that checks a policy — the specs, the harnesses, the vacuity CLI and
shortly the MCP server — reads it through here.

```
.dw text ──> parse ──> policy dicts ──> emit ──> TLA+ records ──> tlc ──> a verdict
               ▲                                        ▲
         schema (pins)                          trace (events)
```

| | |
|---|---|
| `parse.py` | the recursive-descent parser for the modelled Dogwood subset, built against the real `.pest` grammar in the reference tree. Refuses anything outside the subset rather than guessing, and names the *feature* it refused rather than the token it tripped over. Macros are expanded here. |
| `schema.py` | reads an `event.dwschema` for the one thing in it that changes what a policy **means**: a `pin`, which forces a field of every event to equal something about the decision. A policy cannot see or bypass it. |
| `emit.py` | the TLA+ data. Every value is tagged with its kind so TLC refuses a cross-kind comparison instead of quietly answering one. |
| `trace.py` | reads an event log into trace records. `@N` is seconds. |
| `tlc.py` | finds the tools jar by glob, and runs TLC. |
| `dw_to_tla.py` | the script: regenerates `specs/policy/TemporalPolicy/RotationPolicies.tla`. `--check` fails if it has drifted from the `.dw` sources. |

## Why it is a package

It was not one, and the shape of the damage is worth recording because it is the ordinary way a
library fails to appear.

The parser and schema reader sat in `tests/strands/` next to the harnesses that exercised them, and
every TLA+ emitter lived **inside `dogwood_differential.py`** — a test. So `dw_to_tla.py`, whose
output is a checked-in spec, imported `tla_cond` from a test harness, and so did `vacuity.py`, the
tool. Nothing was wrong with the code; the dependency arrow just pointed the wrong way, and would
have kept pointing that way into the MCP server.

Two duplications had already appeared, each character for character, which is what the missing
layer looked like from outside:

- `UNITS` — the second/minute/hour/day table — in both `dogwood_parse.py` and `dogwood_differential.py`.
- `policy_seq` — a policy list as a TLA+ sequence — in both `dw_to_tla.py` and `vacuity.py`.

A third was worse than a duplication. Five harnesses each spelled out the TLC command line, and the
`-Djava.io.tmpdir` flag that stops parallel runs corrupting each other's unpacked standard modules
was missing from **all five** — the C# runner had carried it for a while with a comment explaining
that it cost about one run in four. A copied command line is a command line that drifts. There is
now one `run_tlc`, and the explanation lives with it.

## The boundary

The library translates and runs. It does not decide what to check. Differential harnesses, corpus
walkers and CLIs are consumers and live in their own projects — the test is whether the MCP server
would need it to answer a question about a policy it was handed.

**Nothing here imports from `tests/`.** If that ever reverses, it will show up in `__init__.py`
first.

## Still outside, and arguably misplaced

`tests/strands/vacuity.py` is a product feature — the checker that answers "can this permit ever
grant", "is this rule load-bearing", "do these two policy versions ever disagree" — and it lives in
the test tree. It now *imports* this package rather than its neighbours, so the arrow is no longer
inverted, but its home is still wrong for something the MCP server will expose directly.

Moving it was left out of this change deliberately: it is a **checker**, not a translator, so
dropping it in here would trade one misfiling for another. It probably wants a project of its own.
