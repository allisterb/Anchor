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

---

`traces/` holds the generated model, the configs and the raw TLC output for every
run above, each with a README giving the command to re-run it. `results.json` is the
same findings as data.
