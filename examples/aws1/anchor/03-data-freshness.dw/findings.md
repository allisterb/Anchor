# 01-workflow-sequencing.dw

**Stated intention.** The agent cannot act on a stale quote: a trade must follow a recent market price.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 2 of 3 attempt(s).*

## No property was checked: the draft was rejected at `review`

The gate below is a second model's judgement about whether the claim says what the requirement says. It has no oracle behind it, and it is the one gate here a person may overrule. Nothing downstream ran, and nothing here was verified.

- a second model, shown only the requirement and the plain-English reading of the claim, judged that they do not match:

VERDICT: MISMATCH

The requirement only specifies a restriction—that trades cannot be executed on stale quotes—without requiring the policy to automatically grant every trade with fresh data. The formal claim adds `FreshDataGrants`, which forbids refusing trades when data is fresh (gap ≤ 300), improperly forcing approval regardless of any other conditions or constraints.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 29,231 | 11,917 | 1,865 | 31,096 | 31.3 |
| draft round 2 | 31,045 | 19,830 | 941 | 31,986 | 16.8 |
| the review | 559 | 0 | 503 | 1,062 | 5.8 |
| **3 model call(s)** | **60,835** | **31,747** | **3,309** | **64,144** | **53.9** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft            56.6s
  preflight         0.0s
  score            13.7s
  review            5.8s
  report            0.0s
  total            76.2s
```

Of which 53.9s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
