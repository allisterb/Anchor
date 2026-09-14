# 03-cumulative-cap.dw

**Stated intention.** Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
> - draft round 2 was cut off by the limit_turns cap
> - draft round 3 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `preflight`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the draft did not contain both a module and a .cfg between the ===MODULE=== and ===CONFIG=== markers

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 28,854 | 11,916 | 727 | 29,581 | 18.7 |
| draft round 2 (cut off) | 35,496 | 15,758 | 941 | 36,437 | 20.0 |
| draft round 3 (cut off) | 41,164 | 31,278 | 815 | 41,979 | 21.6 |
| **3 model call(s)** | **105,514** | **58,952** | **2,483** | **107,997** | **60.3** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            60.3s
  preflight         0.0s
  report            0.0s
  total            60.4s
```

Of which 60.3s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
