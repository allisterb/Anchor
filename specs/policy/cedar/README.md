# Cedar

A differential test between a TLA+ model of Cedar's authorization decision and the real engine.

```bash
python tests/strands/cedar_differential.py
```

Needs `cedarpy`, which is pinned and hash-locked like every other Python dependency. It is already
in `requirements/strands/requirements.in`; recompile the lock and install, rather than reaching for a bare
`pip install` that would skip hash checking. See [requirements/strands/README.md](../../../requirements/strands/README.md).

## Why this exists

A TLA+ spec written by reading someone else's code is a paraphrase. Nothing checks that it describes
the real thing, and a wrong model does not fail — it verifies. Translating a declarative artifact is
better, because one file drives both sides, but the translator is still hand-written and can be
wrong in exactly the same way.

So the translation is not trusted, it is tested:

```
policies.cedar ──┬── translate ──> TLA+ policy data ──┐
                 │                                     ├──> TLC checks Agree
                 └── cedarpy ────> oracle table ───────┘
```

Both sides are driven by the same `.cedar` file. The whole finite request space is enumerated, each
request is decided by both the model and the engine, and TLC compares every pair. A disagreement is
reported with the request that caused it:

```
"DISAGREEMENT", [principal |-> [type |-> "Admin", id |-> "root"],
                 action |-> "delete_file", callCount |-> 0],
"model says", "Deny", "engine says", "Allow"
```

| | Trusted by reading? |
|---|---|
| `CedarSemantics.tla` | **Yes** — hand-written, reviewed once. The thing under test. |
| the translator in `cedar_differential.py` | **Yes** — also under test; a mistranslation surfaces as a disagreement exactly as a semantics error would. |
| the oracle | **No** — measured, not asserted. It is the engine's own answer. |

That is the whole point: the surface anyone has to check by reading is one small module and one
parser, and both are held against reality by a test rather than by care.

## The subset modelled

The translator **refuses** anything outside it rather than guessing, because a translator that
silently mishandles a construct yields a model that disagrees with reality in a way the test cannot
attribute.

- `permit` / `forbid`
- principal: unconstrained, `== Type::"id"`, or `is Type`
- action: unconstrained, `== Action::"name"`, or `in [...]`
- resource: **unconstrained only**
- `when { context.session.call_count <op> N }` for `< <= > >= ==`

### Why resource scopes are refused

Strands' `CedarAuthorization` sends `"resource": 'Resource::"agent"'` on every single request —
hardcoded, with no `resource_resolver` in the shipped constructor, though the design doc proposes
one. A resource-scoped policy therefore cannot match anything that handler sends. Modelling such a
policy as unconstrained would make the model agree with the engine in isolation while both diverge
from what the handler can actually express, so the translator stops instead.

This is also why tool-chain escalation is out of reach for this handler: Cedar never learns which
resource a call touches, so no policy can constrain how calls compose.

## Scope

This tests the **policy decision** — a pure function of `(principal, action, context)`. It says
nothing about the enforcement mechanism around it: the increment-then-decrement-on-deny call
counting, or the fact that the rate limiter is safe only because `before_tool_call` happens to be
synchronous and so cannot be interleaved by asyncio.

Those are properties of the handler, not of the policy, and no policy analyser can see them. They
would need a separate model, and one whose tie to reality is trace validation rather than
translation, since there is no declarative artifact to translate.
