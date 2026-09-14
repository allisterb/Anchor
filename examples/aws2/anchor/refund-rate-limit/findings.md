# agent-policy.dw

**Stated intention.** The agent might attempt no more than three refunds against the same account within one hour.

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the property HOLDS, but it also holds of every broken version of this policy that was tried -- rules deleted, permits turned into forbids, conditions dropped. So it is not constraining this policy at all. It is probably ranging over requests the policy never sees, or asserting something trivially true. State the claim about concrete actions and values the policy actually names.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,398 | 3,088 | 9,486 | 21.0 |
| **1 model call(s)** | **6,398** | **3,088** | **9,486** | **21.0** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            29.2s
  preflight         0.0s
  score            18.9s
  report            0.0s
  total            48.2s
```

Of which 21.0s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
