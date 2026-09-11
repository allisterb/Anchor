# Policy fixtures

Real Dogwood policy text, used as **input** by the harnesses in [`../strands`](../strands). Nothing
here is generated and nothing here is a model — these are the files handed to the tooling, and to
the real Dogwood engine, to see what each says about them.

```bash
python src/checker/vacuity.py tests/policies/docs_trading_forbidden.dw
python tests/strands/dogwood_replay.py
```

## Why these are under `tests/` and `rotation_*.dw` is not

`Anchor.Tests.Verifier.csproj` states the rule for the `specs/` tree:

> they are the project's own models, not test fixtures

[`specs/policy/TemporalPolicy/rotation_aggregate.dw`](../../specs/policy/TemporalPolicy/rotation_aggregate.dw)
and `rotation_approval.dw` stay there because `SessionRotation.tla` is **about** them: they are
translated into a checked-in `RotationPolicies.tla` that the spec `EXTENDS`, and the spec's claims
are claims about those two policies. Move them and the spec's subject matter leaves the spec tree.

The files here are the opposite. They exist to exercise the tooling and to demonstrate what it
finds, and any `.dw` file would do as well. A reader looking for *what Anchor asserts* should look
in `specs/`; a reader looking for *what Anchor can be pointed at* should look here.

## What each one is for

| file | used by | what it demonstrates |
|---|---|---|
| [`docs_trading.dw`](docs_trading.dw) | `vacuity.py` | the AgentCore docs' own trading example. Both permits live |
| [`docs_trading_forbidden.dw`](docs_trading_forbidden.dw) | `vacuity.py` | one line different — the sell permit is **vacuous**. Reproduces `TemporalPolicy.tla`'s finding from the text |
| [`approval_gate_response.dw`](approval_gate_response.dw) | `vacuity.py`, `dogwood_replay.py` | gated on a *completed* approval. **Vacuous** on its own |
| [`approval_gate_request.dw`](approval_gate_request.dw) | `vacuity.py`, `dogwood_replay.py` | one word different, and live. The weak form, and the conventional one |
| [`approval_gate_error.dw`](approval_gate_error.dw) | `dogwood_replay.py` | matches the denial itself — rules out "error events are invisible" |
| [`overridden_permit.dw`](overridden_permit.dw) | `vacuity.py` | matches everything, grants nothing. The second shape of vacuity |
| [`dead_forbid.dw`](dead_forbid.dw) | `vacuity.py` | a forbid on an action no permit covers — **DEAD**, it denies nothing |
| [`redundant_permit.dw`](redundant_permit.dw) | `vacuity.py` | a gated permit under an unconditional one — **REDUNDANT**, and pointedly not vacuous |
| [`redundant_permit_minimal.dw`](redundant_permit_minimal.dw) | `vacuity.py --against` | the same file with the redundant rule deleted. Diffs clean, confirming the advice was safe |
| [`added_action.dw`](added_action.dw) | `vacuity.py --against` | permits an action the other file never mentions. Pins the vocabulary union that keeps *no difference* honest |
| [`string_output.dw`](string_output.dw) | `vacuity.py` | a gate on a **string** output field. Was reported VACUOUS when every output was modelled as a boolean — pins that false alarm |
| [`session_gate.dw`](session_gate.dw) | `dogwood_replay.py` | the only fixture here whose **verdict does not depend on its own text**. Replayed unchanged under two shipped event-schema presets it permits under one and denies under the other, because a universal pin partitions the history a temporal predicate can see |
| [`anchor.cedarschema`](anchor.cedarschema) | `dogwood_replay.py` | the Cedar schema the real engine needs to replay a trace |

The three `approval_gate_*.dw` differ by exactly **one word**, which is the point: two of them are
handed to the real engine on identical histories and get opposite verdicts.

## Editing these

They are load-bearing, not illustrative. Assertions in `HarnessTests.cs` name the verdicts these
produce, so changing a policy changes a test result — which is the intended behaviour and is how we
check the files are actually read rather than shadowed by a copy somewhere. Changing
`approval_gate_response.dw` to say `::request` turns the suite red.
