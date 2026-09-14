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
| draft round 1 | 6,401 | 5,191 | 11,592 | 65.5 |
| draft round 2 | 18,117 | 8,679 | 26,796 | 55.0 |
| **2 model call(s)** | **24,518** | **13,870** | **38,388** | **120.5** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft           131.4s
  preflight         0.0s
  score            18.3s
  report            0.0s
  total           149.8s
```

Of which 120.5s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
