# TemporalPolicy

**Vacuity checking for session-aware authorization policies.** Given a policy set, is there any
session at all in which this permit grants something?

A permit that can never fire is a silent deny-everything. It reads correctly, it validates, it
deploys, and the capability it exists to allow is simply gone.

| file | what it is |
|---|---|
| `TemporalPolicy.tla` | the session model and the decision engine |
| `Policies.tla` | the policy set — swappable, like `Workflow.tla` under [`DependencyDAG`](../DependencyDAG) |
| `TemporalPolicy.cfg` | approvals permitted; the sell permit gated on `::response`. **Satisfiable** |
| `Vacuous_ForbiddenApproval.cfg` | approvals forbidden, same permit. **Vacuous** |
| `RequestGated_SurvivesForbid.cfg` | approvals forbidden, permit gated on `::request`. **Satisfiable — and that is the bad news** |

New to TLA+? [`specs/DependencyDAG/README.md`](../DependencyDAG/README.md) has a notation primer.

```bash
java -cp lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config specs/TemporalPolicy/TemporalPolicy.cfg specs/TemporalPolicy/TemporalPolicy.tla
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
the *conventional* form is the weaker one.

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
- **The reference corpus does not exercise the rule the vacuity finding rests on.** Across all 521
  cases in `tests/passing/temporal_only/corpus`, `::error` appears in **zero** policies and **zero**
  traces. The rule is documented in the AgentCore devguide and the finding follows from it, but no
  executable artifact in the reference implementation demonstrates it. Stated as a limit on
  confidence, not as a criticism of their testing.
- **No differential test yet.** A disagreement with the real evaluator would not show up here. The
  corpus is the accessible oracle — each case pairs policies and a trace with recorded expected
  verdicts, and **455 `(trace, expected)` pairs** fall inside the `formerly`-only subset this spec
  already models, needing no Rust build. That has **not** been done.
- **Bounded sessions.** `MaxAttempts = 3`, each attempt being two events. "Vacuous" here means *no
  session of up to three attempts fires it*. A permit needing a longer setup would be reported vacuous when it is merely deep. Raise
  the bound to trade runtime for confidence; this is the ordinary bounded-model-checking caveat and
  it does not go away.
- **One shape of vacuity.** A permit that fires but is always overridden by a `forbid` grants
  nothing either. `Granted` distinguishes matched from granted, so that case is detectable, but no
  config here exercises it.
- **Nothing about the rest of the policy.** Time-based conditions, `count`/`sum` aggregations,
  `since within`, entity tags and multi-hop session propagation are all unmodelled.
