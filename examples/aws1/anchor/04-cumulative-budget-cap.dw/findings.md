# 01-workflow-sequencing.dw

**Stated intention.** No single session can exceed $60,000 in total trade value.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 3 of 3 attempt(s).*

## No property was checked: the draft was rejected at `review`

The gate below is a second model's judgement about whether the claim says what the requirement says. It has no oracle behind it, and it is the one gate here a person may overrule. Nothing downstream ran, and nothing here was verified.

- a second model, shown only the requirement and the plain-English reading of the claim, judged that they do not match:

VERDICT: MISMATCH

The formal claim requires refusing trades whenever the sum `a1 + a2` exceeds $60,000 regardless of the time gap between them (applying equally to `gap = 10` and `gap = 400`). This enforces a global cap across trades rather than scoping the $60,000 limit to trades occurring within a single session.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 29,870 | 11,927 | 1,053 | 30,923 | 26.1 |
| draft round 2 | 27,891 | 15,810 | 1,581 | 29,472 | 32.9 |
| draft round 3 | 35,430 | 23,749 | 2,062 | 37,492 | 24.5 |
| the review | 809 | 0 | 613 | 1,422 | 6.0 |
| **4 model call(s)** | **94,000** | **51,486** | **5,309** | **99,309** | **89.5** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft           105.5s
  preflight         0.0s
  score             3.2s
  review            6.0s
  report            0.0s
  total           114.7s
```

Of which 89.5s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
