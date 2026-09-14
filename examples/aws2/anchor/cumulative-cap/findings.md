# agent-policy.dw

**Stated intention.** Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

*Drafted in 2 of 3 attempt(s).*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,404 | 6,667 | 13,071 | 35.3 |
| draft round 2 | 19,594 | 5,036 | 24,630 | 55.7 |
| **2 model call(s)** | **25,998** | **11,703** | **37,701** | **91.1** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft           109.3s
  preflight         0.0s
  score            24.4s
  report            0.0s
  total           133.8s
```

Of which 91.1s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
