# Findings — `aws1`

**7 thing(s) to look at.**

1. **agent-policy.dw does not satisfy TradeGate.tla** — a stated intention is not met
2. **07-trust-decay.dw does not satisfy TrustDecay.tla** — a stated intention is not met
3. **07-trust-decay.dw does not satisfy TrustDecay10.tla** — a stated intention is not met
4. **01-workflow-sequencing.dw: VACUOUS permit #1** — because `formerly within 5m get_client_profile::response`
5. **01-workflow-sequencing.dw: VACUOUS permit #2** — because `formerly within 5m load_portfolio::response`
6. **02-output-to-input.dw: VACUOUS permit #1** — because `formerly within 24h get_client_profile::response{ input.profile_id: 'profile_id' }`
7. **03-data-freshness.dw: VACUOUS permit #1** — because `formerly within 30s get_market_price::response`

## What was checked

| | |
|---|---|
| policies | 5 |
| stated intentions (`.tla`) | 3 |
| questions answered | 0 |

## Per policy

| policy | rules | verdicts |
|---|---|---|
| `01-workflow-sequencing.dw` | 2 | VACUOUS |
| `02-output-to-input.dw` | 1 | VACUOUS |
| `03-data-freshness.dw` | 1 | VACUOUS |
| `07-trust-decay.dw` | 1 | live |
| `agent-policy.dw` | 7 | live |

## Stated intentions

| policy | module | |
|---|---|---|
| `agent-policy.dw` | `TradeGate.tla` | **BROKEN** |
| `07-trust-decay.dw` | `TrustDecay.tla` | **BROKEN** |
| `07-trust-decay.dw` | `TrustDecay10.tla` | **BROKEN** |

### What each of them forbids

Read these before the verdicts above. Each line is the only thing its claim
can catch — a claim that forbids nothing you object to passes without having
tested what you meant.

**`TradeGate.tla`** — 5 state(s), enumerated from `Init`

- `FreshPriceAloneIsNotEnough` forbids: prereq is "freshPriceOnly", and yet the policy GRANTS it (Allowed(prereq)) _(its condition applies to 1 of 5 states)_
- _defined but not named in the `.cfg`, so never checked:_ `BothIsAllowed`, `NothingAllowsNoTrade`, `ProfileAloneIsNotEnough`, `RequiresBothChecks`

**`TrustDecay.tla`** — 6 state(s), enumerated from `Init`

- `LosesWriteAfter15m` forbids: gap is greater than 15 * Minute (= 900), and yet the policy GRANTS it (TradeAllowed(gap)) _(its condition applies to 2 of 6 states)_
- `KeepsWriteWhileAdvisorEngaged` forbids: gap is at most 15 * Minute (= 900), and yet the policy REFUSES it (TradeAllowed(gap)) _(its condition applies to 4 of 6 states)_
- `LosesWriteAfter10m` forbids: gap is greater than 10 * Minute (= 600), and yet the policy GRANTS it (TradeAllowed(gap)) _(its condition applies to 3 of 6 states)_

**`TrustDecay10.tla`** — 6 state(s), enumerated from `Init`

- `LosesWriteAfter10m` forbids: gap is greater than 10 * Minute (= 600), and yet the policy GRANTS it (TradeAllowed(gap)) _(its condition applies to 3 of 6 states)_

---

`traces/` holds the generated model, the configs and the raw TLC output for every
run above, each with a README giving the command to re-run it. `results.json` is the
same findings as data.
