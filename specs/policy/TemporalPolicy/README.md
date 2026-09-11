# TemporalPolicy

**Vacuity checking for session-aware authorization policies.** Given a policy set, is there any
session at all in which this permit grants something?

A permit that can never fire is a silent deny-everything. It reads correctly, it validates, it
deploys, and the capability it exists to allow is simply gone.

**Point it at any `.dw` file:**

```bash
python tests/strands/vacuity.py tests/policies/docs_trading_forbidden.dw
```
```
docs_trading_forbidden.dw: 1 permit(s), 1 forbid(s), bound 3 attempts

  permit #2  action == SellShares    VACUOUS   no session of up to 3 attempts makes it grant
```

Nothing about that policy is hand-modelled — see
[the checker](#the-checker-takes-arbitrary-policy-text) below.

| file | what it is |
|---|---|
| `Vacuity.tla` | **the generic checker**: any parsed policy, any permit, evaluated by `DogwoodSemantics` |
| `TemporalPolicy.tla` | the original, hand-written: its own session model and its own decision engine |
| `DogwoodSemantics.tla` | our reading of `formerly within`, checked against the reference corpus |
| `Policies.tla` | the policy set — swappable, like `Workflow.tla` under [`DependencyDAG`](../../strands/DependencyDAG) |
| `TemporalPolicy.cfg` | approvals permitted; the sell permit gated on `::response`. **Satisfiable** |
| `Vacuous_ForbiddenApproval.cfg` | approvals forbidden, same permit. **Vacuous** |
| `RequestGated_SurvivesForbid.cfg` | approvals forbidden, permit gated on `::request`. **Satisfiable — and that is the bad news** |
| `SessionRotation.tla` | what a caller who controls the session id can do |
| `SessionRotation.cfg` | aggregate cap, rotation allowed. **Cap violated** |
| `NoRotation_CapHolds.cfg` | the control: same policy, rotation disabled. Cap holds |
| `Rotation_ApprovalGateHolds.cfg` | approval gate, rotation allowed. Gate holds |

And the policy inputs — real Dogwood text, checked in, which is what the tooling reads:

| `.dw` file | what it demonstrates |
|---|---|
| [`docs_trading.dw`](../../../tests/policies/docs_trading.dw) | the AgentCore docs' own trading example. Both permits live |
| [`docs_trading_forbidden.dw`](../../../tests/policies/docs_trading_forbidden.dw) | one line different. **The sell permit is vacuous** |
| [`approval_gate_response.dw`](../../../tests/policies/approval_gate_response.dw) | gated on a completed approval. **Vacuous** on its own |
| [`approval_gate_request.dw`](../../../tests/policies/approval_gate_request.dw) | one word different. Live |
| [`approval_gate_error.dw`](../../../tests/policies/approval_gate_error.dw) | matches the denial itself. Live |
| [`overridden_permit.dw`](../../../tests/policies/overridden_permit.dw) | matches everything, grants nothing. **Vacuous**, second shape |
| [`rotation_aggregate.dw`](rotation_aggregate.dw) | the spend cap `SessionRotation` defeats |
| [`rotation_approval.dw`](rotation_approval.dw) | the approval gate it cannot |

New to TLA+? [`specs/strands/DependencyDAG/README.md`](../../strands/DependencyDAG/README.md) has a notation primer.

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config specs/policy/TemporalPolicy/TemporalPolicy.cfg specs/policy/TemporalPolicy/TemporalPolicy.tla
```

## Read the result backwards

This spec checks `NeverFires`, and **means it to fail**:

| TLC says | means |
|---|---|
| **Invariant violated** | the permit is **satisfiable**, and the counterexample is the *witness session* proving it |
| **No error found** | the permit is **vacuous**. This is the bad outcome, and it is the quiet one |

TLA+ is linear-time and has no `EF`, so reachability is posed as the negation of an invariant and
the trace is read as the witness. Everywhere else in this repo that is a workaround; here it is the
whole tool.

**The configs are only meaningful together.** A check that can only ever report "no violation"
proves nothing — a broken engine in which nothing ever fires would pass the vacuity check trivially.
The two satisfiable configs are the control: they demonstrate the machinery *can* find a witness,
which is what makes the absence of one in `Vacuous_ForbiddenApproval` informative.

## Why this exists

AgentCore's temporal policies — written in **Dogwood**, a Cedar superset — decide using the history
of a session rather than the current request alone. From the announcement's own limitations:

> temporal conditions do not currently support the powerful automated reasoning analysis tools that
> Cedar provides

Cedar has symbolic analysis: equivalence, subsumption, satisfiability. Temporal policies have none
of it. So Dogwood **enforces** a policy on the session that happens, and nothing checks that the
policy set means what its author intended across the sessions that could happen. That second thing
is model checking.

## The finding this reproduces

The policy is the trading example from the AgentCore docs:

```
permit (principal, action == "SellShares", resource == gateway)
when temporal {
    formerly within 1h Action::"ApproveSale"::response{
        input.stock:     context.input.stock,
        output.approved: true
    }
};
```

Now add one unrelated rule — approvals are tightened, by someone who never read the sell rule:

```
forbid (principal, action == "ApproveSale", resource);
```

The SellShares permit is **untouched**. It still parses, still validates, still references a real
action. And it can never fire again, because:

> a permitted action that completes is recorded as a `response` event, and an action that a policy
> denies is recorded as an `error` event. A temporal condition matches only events of the kind it
> names

`::response` never matches, so the condition is unsatisfiable, so the permit is dead. **Nothing
about either policy read on its own says so** — it is a property of the set, and that is exactly
what per-policy review misses and a model checker does not.

```
TemporalPolicy                   SATISFIABLE
Vacuous_ForbiddenApproval        VACUOUS
RequestGated_SurvivesForbid      SATISFIABLE
```

## One word apart, opposite security properties

That third row is the sharper finding, and it came out of reading the reference corpus.

AgentCore records a `request` event for **every** attempt, permitted or not; only the outcome
differs — `response` when allowed, `error` when denied. So these two gates are not variations on a
theme:

| gate | matches | survives `forbid ApproveSale`? |
|---|---|---|
| `ApproveSale::response{...}` | an approval that was permitted **and completed** | no — goes vacuous |
| `ApproveSale::request{...}` | somebody **tried** to get an approval | **yes** — fires on denied attempts |

The second reads like an approval gate and is not one. It grants precisely the capability the
approval existed to protect, off a sequence of refusals. Same engine, same policy set, same forbid —
the event kind is doing all the work.

The corpus made this visible: `::request` appears in 555 policy files against `::response`'s 94, so
the *conventional* form is the weaker one. It does not, however, contain a single `::error`, so for
a while this table was read off the devguide rather than executed. It is executed now — the built
engine returns DENY for the first row and ALLOW for the second, on the same denied approval. See
[The engine judges traces the corpus never recorded](#the-engine-judges-traces-the-corpus-never-recorded).

## What is modelled

Enough MFOTL to pose the question honestly:

| | |
|---|---|
| **metric** | `Window` — a bounded look-back, standing for `within 1h` |
| **first-order** | the correlation `hist[i].stock = req.stock`. Not "some approval happened" but "an approval for **this** stock". A propositional temporal logic cannot express that join, and it is the whole reason the logic is first-order |
| **past-time** | history only. An authorizer decides *now*, from what has already happened — you cannot gate a permit on a future obligation without blocking |

The agent is not modelled: it attempts any request at any time, and `ApproveSale` may return either
verdict. Both are behaviours, so a result holds whatever the agent and the approver do — the same
stance every other spec here takes.

## What this does not establish

- **It is not a model of Dogwood, and it models two layers at once.** Dogwood the *language* has no
  fixed event vocabulary — its grammar says "event kinds are author-defined, not a fixed set —
  `request` / `response` are merely the conventional ones", and a schema marks one of them the
  `decision event`. `error` is not a Dogwood concept at all: it is **AgentCore's** convention for
  recording a denied action. `Policies.tla` holds the schema-declared vocabulary to keep the two
  visibly separate, but every finding here is about the service convention, not the language.
- **The `error` rule is confirmed by the engine, not by the corpus.** Across all 521 cases in
  `tests/passing/temporal_only/corpus`, `::error` appears in **zero** policies and **zero** traces,
  so for a long time the finding rested on the devguide alone. It no longer does: the built engine
  judges traces we construct, and it agrees — see [below](#the-engine-judges-traces-the-corpus-never-recorded).
  What that costs is that the check needs a compiled binary, so it skips where the corpus half runs
  anywhere.
- **The differential test covers `DogwoodSemantics.tla`, not this spec.** `formerly within` as read
  here now agrees with the reference implementation on **774 recorded pairs** — see below. What is
  still unchecked is most of what this spec adds on top: the session model and `Granted`. The
  request/response/error recording convention is the exception — the replay harness puts that one
  in front of the engine directly.
- **Bounded sessions.** `MaxAttempts = 3`, each attempt being two events. "Vacuous" here means *no
  session of up to three attempts fires it*. A permit needing a longer setup would be reported vacuous when it is merely deep. Raise
  the bound to trade runtime for confidence; this is the ordinary bounded-model-checking caveat and
  it does not go away.
- **~~One shape of vacuity.~~** Both shapes are now checked. A permit that *matches* but is always
  overridden by a `forbid` grants nothing either, and a condition-satisfiability check cannot see
  it — the condition is satisfiable, the permit is inert. `Granted` separates matched from granted,
  and [`overridden_permit.dw`](../../../tests/policies/overridden_permit.dw) exercises it. Mutation-checked: drop the
  `Allowed` guard from `Granted` and that file reports live.
- **Nothing about the rest of the policy.** Time-based conditions, `count`/`sum` aggregations,
  `since within`, entity tags and multi-hop session propagation are all unmodelled.


## Checked against the reference implementation

The largest caveat on this spec used to be that it modelled the *documented* rules with nothing
confirming the reading. Dogwood's own repository closes it: its temporal regression corpus is 521
cases, each pairing a policy set and an event trace with **the verdicts their engine produced**.

```bash
python tests/strands/dogwood_differential.py
```

```
checked   774 (trace, expected) pairs from 389 cases, in one TLC run
  AGREE
```

The subset covers `formerly within`, `previous within`, `since within`, `&&`, `!`, `when`/`unless
temporal`, and the `count`/`sum` aggregations with `tp()` timepoint binders. Every construct is
genuinely exercised, so the agreement means something for each rather than resting on the common
one:

| construct | accepted cases using it |
|---|---|
| `formerly` | 254 |
| `since` | 68 |
| `tp()` | 55 |
| `sum` | 36 |
| `previous` | 34 |
| `count` | 24 |

**None of these has documented semantics we could find.** They are written as standard past-time
MFOTL and the corpus is the only reason to believe that reading — so each is mutation-checked
independently, and all six turn the run red:

```
window (metric bound)    caught      tp binding               caught
previous index           caught      count vs sum             caught
since continuity         caught      self-inclusion (upto)    caught
```

### How `count` was decoded

Corpus case 0254 is the Rosetta stone. Four identical transfers, and:

```
exists (n: Long). ((count for (t: Timepoint).
    where (formerly within 1h (Transfer::request{...} && tp(t)))) == n && n >= 3)
```

Expected verdicts are `true, true, false, false`. That only works if `count` counts **distinct
assignments to the bound variables** — here timepoints, via `tp(t)` — and if the request being
authorized counts itself. Both fall straight out of the flip on the third transfer.

Nothing is built or run for *this* harness — the expected outputs are recorded, so the corpus is
data. (The replay harness below does build the CLI, under the checks in the reference ledger.)
Either way no network is touched and no credentials exist.

**The refusal count matters as much as the agreement count.** 132 cases are outside the modelled
subset and are refused rather than approximated, because a translator that quietly mishandles a
construct yields a disagreement it cannot attribute.

The subset was widened on 2026-09-11, from 654 pairs / 320 cases to **774 pairs / 372 cases**, by
adding three constructs:

| construct | example | cases |
|---|---|---|
| a parenthesised left operand of `since` | `!(Login::response{..}) since within 1h Sync::request{..}` | 13 |
| a comparison on the request's own context | `formerly within 1h (Login::request{..} && context.input.amount > 100)` | 24 |
| an aggregate body with **no** temporal wrapper | `count for (t: Timepoint). where (Login::request{..} && tp(t))` | 36 |
| an event schema that **pins** a scope field into every predicate | `pin callerPrincipal: principalType(A) = principal` | 20 |
| a pin on a nested reserved leaf | `__drupe: { pin session_id: String = context.__drupe.session_id }` | 3 |

The first needed **no semantics at all** — `DogwoodSemantics` already carried `left`/`leftNeg`; the
parser had simply committed to reading `!(` as a negated group before anything looked for the
`since` after it. The second is a genuine addition: a `cmp` atom that reads the **decision** event
rather than the candidate one, so it evaluates identically at every candidate index and filters the
request rather than the history.

All three were chosen because their cases *discriminate*: 13 of 13, 22 of 24 and 24 of 36 have a
`true` somewhere in their expected output. A case whose every verdict is false is nearly worthless
as evidence, since a reading that never matches anything passes it too.

**The third shows why that test earns its keep.** `0178_agg_no_temporal_counts_current_tp` states
the rule in its own comment — *"Without a temporal wrapper on the body, the aggregation sees only
same-tp events"* — and every one of its verdicts is `false`, so it cannot tell that reading apart
from one that matches nothing. `0062_count_exact` settles it instead. Its policy **set** holds both
`n == 2` and `n == 0`, and only "this timepoint" reproduces all five verdicts:

| decision | Logins at that timepoint | count | matches | expected |
|---|---|---|---|---|
| @0 Login | the Login itself | 1 | neither | false |
| @4 Alert | none | **0** | `n == 0` | **true** |
| @12 Alert | none | **0** | `n == 0` | **true** |

Counting the whole history instead gives 3 at @12, where the expected answer needs 0.

A timepoint is a trace **index**, not a timestamp — the corpus prints `@12 (time point 8)` for one
event — so "same tp" is the decision event's own index. Mutating the `at` arm to search `1..upto`,
which is exactly that competing reading, turns the run red: the semantics is held up by the corpus
rather than by one person's reading of one case.

**132 cases still stand refused**: macro calls and parameter sigils, the 30 schema-pin cases,
`since` nested inside an aggregate body, `count`/`sum` bodies written without parentheses,
comparisons against something other than a literal, and ten `Long` values outside TLC's integer
range, which no amount of modelling will fix.

**`SessionRotation` checks a real Dogwood policy, end to end.** Neither the decision nor the
policy is written in that spec any more:

```
rotation_*.dw ──> dogwood_parse ──> RotationPolicies.tla ──┐
                                                           ├──> TLC checks the properties
                             SessionRotation.tla ──────────┘
```

The policy is [`rotation_aggregate.dw`](rotation_aggregate.dw) and
[`rotation_approval.dw`](rotation_approval.dw) — Dogwood text — translated by the same parser whose
reading agrees with the reference implementation on 774 corpus cases, and evaluated by the same
`DogwoodSemantics!Decide`. Even the cap is lifted from the policy text into `Cap`, so the property
and the rule cannot disagree about what the limit is.

Two earlier versions each hand-wrote one half of this and each time the finding rested on something
unchecked: first a hand-rolled `SumTrades`, then policy records nobody had compared against the
Dogwood text in their own comment. The only thing the spec still asserts on its own is the
adversary.

**The wiring is live, demonstrated by editing the policy text rather than the model:**

| `.dw` edit | `Cap` | rotation | control |
|---|---|---|---|
| baseline | 3 | VIOLATED | HOLDS |
| `n > 3` becomes `n > 100` | **100** | **HOLDS** | HOLDS |
| `forbid` becomes `permit` | 3 | VIOLATED | **VIOLATED** |

`RotationPolicies.tla` is generated and checked in — which is what lets the spec tests run in CI
without a venv — so `dw_to_tla.py --check` regenerates and compares, and the suite fails on drift.

### What it caught on the first run

Two disagreements, and both were ours.

A case whose `event.dwschema` declares:

```
pin callerPrincipal: principalType(A) = principal
```

The schema comment says what that does: *"The policy never writes `callerPrincipal`; the pin injects
it, so the correlation cannot be bypassed by a directly-written predicate."*

In that case's second trace, **bob logs in claiming to be alice**, then alice reads. The written
condition matches — `input.user` correlates alice to alice — and Dogwood denies anyway, because the
pin requires the login's `callerPrincipal` to equal the reader's `principal`.

**A policy's meaning is not determined by its own text.** Reading the `.dw` and ignoring the schema
is exactly the silent mishandling this harness exists to prevent, so schema-bearing cases are now
refused. Modelling pins would be a real extension, and it is not done.

The harness is mutation-checked: removing the metric bound from `TermHolds` turns the run red.


## A policy's meaning is not in its own text

The sharpest thing the corpus taught us, and the thing that caught our translator on its first run.

An `event.dwschema` can **pin** a field, forcing every event's copy of it to equal something about
the decision:

```
decision event <A>::request {
    ...inputs(A),
    pin callerPrincipal: principalType(A) = principal,
}
```

The policy never writes `callerPrincipal`, cannot see it, and cannot bypass it. In
`1117_pin_principal_correlation` the written condition correlates on `input.user` and matches —
and the engine denies anyway, because the pin requires the prior Login's principal to equal the
reader's. Read the `.dw` and ignore the schema and you get a different answer than the engine.

### Universal versus partial, which is the half that bites

A pin declared on **every** event kind is *universal* and switches the leaf to key-local
semantics: the trace is partitioned by the pinned key and temporal operators see only the
decision's own partition. A pin declared on **some** kinds is *partial*, earns no isolation, and
stays global. The corpus puts it plainly — "the engine must not grant isolation the schema did not
earn."

The distinction is invisible to `formerly`, `count` and `sum`. They are existential, so restricting
the candidates is the same as adding a conjunct, and an implementation that only injected conjuncts
would pass every one of those cases.

It is visible to **`previous`**, which means *the most recent match*:

| | global (partial pin) | partitioned (universal pin) |
|---|---|---|
| a foreign event is the most recent | it **is** the `previous`, and fails the predicate → deny | skipped entirely → the most recent of *mine* is used → permit |

`1155_relativize_previous_ignores_foreign` and `1164_partial_pin_stays_global` are **the same
policy and the same trace**, differing only in whether the pin covers both event kinds — and they
have opposite verdicts. That pair is why pins are modelled as partitioning rather than as injected
conjuncts, and both directions are mutation-checked: treating every pin as universal turns the run
red, and so does dropping partitioning and keeping the conjuncts.

### What is modelled, and what is refused

Universal and partial pins on the two **scope** fields, `callerPrincipal` and `callerResource`,
plus universal pins on the nested reserved leaf `__drupe.session_id`. That last one partitions by
**session** — it confines a policy to its own session without the policy ever mentioning sessions —
and `1158_relativize_two_pins_both_required` pins it *alongside* `callerPrincipal`, so two keys must
hold at once.

`1122_pin_disagree_denies_despite_author_literal` is the other half of the contract, and it needed no
rule of its own. The policy writes `__drupe.session_id: "sess-1"` itself; partitioning already
confines candidates to the decision's own session, so an author literal naming a different one leaves
nothing that can satisfy both — the permit is unsatisfiable rather than merely unmatched.

Refused, each being a separate feature rather than a spelling of this one:

- pins on a context field, `pin tenant_id: String = context.tenant_id`
- deeper paths under `__drupe` than the single `session_id` leaf
- schemas with custom event kinds (`attempt`/`outcome` instead of `request`/`response`)
- the **nine** schema-bearing cases with no pin at all, which are in the corpus for renamed
  reserved fields, deep paths and injected slots

That last group is worth naming: the old refusal message said "event schema pins a field into every
predicate" for all 30 schema cases, and a third of them contain no pin. The message now says which
feature actually stopped it.

**Two assumptions, stated because they are load-bearing.** Each was checked across the whole
corpus rather than assumed, and either would make the model *wrong* rather than merely
incomplete if a trace broke it:

| assumption | checked |
|---|---|
| an event's `callerPrincipal` is its `scope(...)` principal | 4371 events, never diverge |
| a decision's `context.__drupe.session_id` is its own payload's | 20 decision events, never diverge |

The model reads the second of each pair.


## The checker takes arbitrary policy text

For a long time this directory model-checked *one* policy, hand-written into `Policies.tla` as a
`PermitFires` CASE expression. That is a paraphrase, and nothing checks a paraphrase. `Vacuity.tla`
removes both hand-written halves:

```
any .dw ──> dogwood_parse ──> PolicyUnderTest.tla ──┐
                                                    ├──> TLC, once per permit
                          Vacuity.tla ──────────────┘
```

- The **policies** come from the parser that agrees with the reference implementation on 774
  recorded corpus pairs, so what is checked is the policy as written.
- The **decision** is `DogwoodSemantics!Decide` — the same evaluator, validated against those pairs
  and against the live engine on the `error` scenarios.
- The **vocabulary** is lifted from the policy too: only the actions, event kinds and input/output
  fields some condition actually reads get modelled, so a policy that joins on nothing costs
  nothing to check.

What is left hand-written is the *session model* — that an attempt records a decision event and
then an outcome, and that the outcome kind is `response` when allowed and `error` when denied.
That is AgentCore's convention rather than the policy's content, and it is the thing the replay
harness checks against the real engine.

### It reproduces the hand-written spec's finding

The strongest evidence that the generalisation is faithful. `docs_trading.dw` is the AgentCore
documentation's trading example — the same policy `TemporalPolicy.tla` models by hand:

```
docs_trading.dw            permit #1  action == ApproveSale   live      witness: ApproveSale
                           permit #2  action == SellShares    live      witness: ApproveSale -> SellShares

docs_trading_forbidden.dw  permit #2  action == SellShares    VACUOUS
```

Same result as `Vacuous_ForbiddenApproval.cfg` reaches through the hand-written model. The two
share no code on the path that matters — different policy representation, different decision
function — so this is a cross-check rather than a restatement. Both specs stay in the tree for
exactly that reason.

It also exercises the two constructs the smaller cases do not: the first-order join
(`input.stock: context.input.stock` — *an approval for **this** stock*, which a propositional
temporal logic cannot express) and an output-field bind (`output.approved: true`).

### The two shapes of vacuity

| shape | example | why a satisfiability check misses it |
|---|---|---|
| the condition can never hold | `approval_gate_response.dw` | the condition is satisfiable *in principle* — it just needs an event this policy set can never produce |
| it holds, and a `forbid` wins | `overridden_permit.dw` | the condition is `true`. The permit matches every request and grants none |

The second is why the spec tracks **granted** rather than **matched**. `Granted` returns the
matching permits only when the request was actually allowed; counting a matched-but-overridden
permit as live would report an inert policy as working.

### Reading a VACUOUS verdict honestly

**VACUOUS is bounded, and it is the direction that must never be wrong.** It means *no session of
up to `--attempts` attempts makes this permit grant*, not *never*. A permit needing a longer setup
is reported vacuous when it is merely deep — and that is the dangerous error, because it would send
someone to delete a control that works. Three things are done about it:

- The verdict is **falsification-tested**, not merely observed. Adding `permit (action ==
  ApproveSale)` to `approval_gate_response.dw` flips it to live, so the VACUOUS is attributable to
  the approval being denied rather than to the model being unable to reach a `response` at all.
- Anything that is **not an answer** — a parse error, an unsupported construct, a `TypeOK` failure
  — raises rather than being reported as vacuous. Silence must never read as a finding.
- Constructs outside the modelled subset are **refused**, with the reason. A policy reading two
  input fields is refused rather than checked, because every input field shares one numeric domain
  in the model and two would silently under-explore:

```
REFUSED: two_fields.dw is outside the modelled subset
  policy reads 2 input fields (amount, stock); the model gives every input field one shared
  domain, so this would under-explore
```

A `live` verdict needs no such care: it comes with a witness session, which is evidence rather
than an absence.

### Mutation-checked

| mutation | what breaks |
|---|---|
| `Granted` drops its `Allowed` guard | `overridden_permit.dw` reports live |
| denied attempts recorded as `response` | `approval_gate_response.dw` reports live |

Both are in the test suite's assertions, so either turns the build red rather than merely changing
a printout.


## The engine judges traces the corpus never recorded

The corpus is a large oracle but a fixed one: it answers only about traces Amazon happened to
record, and the blind spot is the one place this spec most needs an answer. Building `dogwood-cli`
turns the oracle live — it will judge any trace we hand it, including event kinds the corpus never
uses.

```
approval_gate_*.dw ─┬─ dogwood replay ─────────────────────────> verdicts (the oracle)
                    └─ dogwood_parse ──> TLA+ ──> TLC ─────────> our verdicts
```

Both sides read the same policy file, so a disagreement is ours. The three gates are checked in and
differ by exactly one word:

| policy | gate | what it is for |
|---|---|---|
| [`approval_gate_response.dw`](../../../tests/policies/approval_gate_response.dw) | `Approve::response` | the strong form — requires an approval that completed |
| [`approval_gate_request.dw`](../../../tests/policies/approval_gate_request.dw) | `Approve::request` | the weak form, and the conventional one |
| [`approval_gate_error.dw`](../../../tests/policies/approval_gate_error.dw) | `Approve::error` | rules out the duller explanation, below |

[`dogwood_replay.py`](../../../tests/strands/dogwood_replay.py) runs five scenarios over them. The
traces are generated in the harness — they are the history to evaluate against, where the policies
are what is under test. The engine's verdicts, which are what the run prints:

| policy | history | verdict at the trade | what it settles |
|---|---|---|---|
| `..._response.dw` | approval **denied** | **DENY** | an `error` is not a `response`, so the gate stays shut |
| `..._request.dw` | approval **denied** | **ALLOW** | the attempt was recorded, so the weaker gate opens — the finding |
| `..._response.dw` | approval allowed | ALLOW | the control: with a real response the same gate opens |
| `..._response.dw` | nothing at all | DENY | deny by default |
| `..._error.dw` | approval **denied** | ALLOW | a policy *can* match error events, if it says so |

The second row is the whole point. Two policies one word apart, opposite security properties, and
the difference is invisible to a syntax checker because both parse and both are satisfiable. Rows
one and two together are the claim: it is not that a denied approval is unrecorded, it is that it is
recorded *under a different kind*.

The fifth row earns its place. Without it, "the response gate stays shut" is also consistent with
`error` events being invisible to temporal matching altogether, which would be a fact about the
engine rather than about AgentCore's recording convention. It is the convention.

Our semantics agrees with the engine on all five. Mutation-checked three ways: making `Matches`
ignore the event kind, making `error` count as a `response`, and editing `approval_gate_response.dw`
to say `::request` — that last one flips the first row to ALLOW and fails the C# assertion, which is
what shows the checked-in policy is the thing being judged rather than a copy of it.

It needs the built binary, which is not in the repo, so
`PythonHarnessAttribute.RequiresExecutable` skips the C# test rather than failing it when the tree has not
been built. Build it with no feature flags. The `net` feature would make evaluation
non-deterministic and network-dependent, which is exactly what this spec assumes away; it cannot
arrive by accident, only via `--features net` or `--all-features`.

```
cargo build --release --locked --manifest-path ext/dogwood/Cargo.toml
```


## Session rotation, and which policy shapes survive it

AgentCore scopes temporal history to a **policy session**, and the session id travels in a
caller-supplied header. AWS says what follows, in their own security considerations:

> Because temporal history is scoped to a session and the session ID is supplied by the caller, a
> `count`-based limit such as "at most N calls per session" counts only the events recorded for that
> session. Starting a new session begins a new count, so a temporal rate limit constrains activity
> within a session rather than across all of a caller's sessions.

So the behaviour is documented and this is **not a discovery**. What it adds is a trace, and a
finding about policy *shapes* that is not written down anywhere.

```
SessionRotation                VIOLATED: Invariant GlobalCapHolds is violated.
NoRotation_CapHolds            HOLDS
Rotation_ApprovalGateHolds     HOLDS
```

The attack is three steps, against a cap of 3:

```
State 2: hist = <<[action |-> "Trade", amount |-> 2]>>   traded = 2
State 3: hist = <<>>                                     traded = 2     \* rotate
State 4: hist = <<[action |-> "Trade", amount |-> 2]>>   traded = 4
```

**The control is the load-bearing half.** `NoRotation_CapHolds` runs the same policy and the same
adversary with rotation disabled, and the cap holds. Without it the violation could be any modelling
error; with it, rotation is the only thing that differs.

It doubles as proof that the aggregate is live: if the `forbid` never fired, the cap would be
breached without any rotation at all. Mutation-checked both ways — making the forbid unreachable, or
summing over the timepoint binder instead of the amount, each breaks the control.

### The asymmetry

On a fresh trajectory the history is empty, and the two policy shapes go in opposite directions from
that single cause:

| shape | on an empty trajectory | |
|---|---|---|
| **permit** gated on a prior event | does not fire → default deny | **fails closed** — rotation costs the caller the capability |
| **forbid** on an aggregate (`count`, `sum`) | sees zero → does not fire → allowed | **fails open** — rotation hands the caller a fresh allowance |

Budget caps, rate limits and mutual-exclusion rules are all the second shape. Approval gates are the
first. Of the seven policies in the AgentCore banking example, roughly four are aggregates.

**Self-referential inclusion is modelled**, because AgentCore documents that "when a temporal
condition references the same action that is being authorized, the current request's own event is
included in the evaluation". The aggregate therefore counts the trade being decided, which is what
makes the cap bite at the right point rather than one trade late.

### What this does not establish

- **The policy is real Dogwood, but the *trace* is ours.** Events are synthesised by this spec in
  the shape `DogwoodSemantics` expects; nothing checks that AgentCore records a session the same
  way. The corpus validates the evaluator against recorded traces, not our construction of new
  ones.
- **Bounded.** Six steps, a cap of 3, trades of 1–2. Enough to exhibit the attack, not a claim about
  larger configurations.
- **Rotation is modelled as free.** In reality a caller must be able to set the header, and a
  deployment that derives the session id server-side would not have this exposure at all. Whether
  that is possible is a deployment question this spec cannot see.
