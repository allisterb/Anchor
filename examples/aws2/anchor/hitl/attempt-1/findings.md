# agent-policy.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

*Drafted in 2 of 3 attempt(s).*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 | 6,399 | 0 | 5,456 | 11,855 | 46.4 |
| draft round 2 | 12,189 | 4,077 | 5,744 | 17,933 | 48.0 |
| **2 model call(s)** | **18,588** | **4,077** | **11,200** | **29,788** | **94.4** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft           106.1s
  preflight         0.0s
  score            19.5s
  report            0.0s
  total           125.8s
```

Of which 94.4s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
