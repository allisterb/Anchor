# agent-policy.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

*Drafted in 2 of 3 attempt(s).*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,399 | 6,580 | 12,979 | 38.2 |
| draft round 2 | 19,501 | 12,878 | 32,379 | 75.0 |
| **2 model call(s)** | **25,900** | **19,458** | **45,358** | **113.3** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft           125.0s
  preflight         0.0s
  score            19.0s
  report            0.0s
  total           144.2s
```

Of which 113.3s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
