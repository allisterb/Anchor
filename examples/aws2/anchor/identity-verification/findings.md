# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,405 | 4,384 | 10,789 | 27.8 |
| **1 model call(s)** | **6,405** | **4,384** | **10,789** | **27.8** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            36.7s
  preflight         0.0s
  score            24.9s
  report            0.0s
  total            61.7s
```

Of which 27.8s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
