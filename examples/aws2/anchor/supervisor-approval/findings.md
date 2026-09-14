# agent-policy.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
no --event-schema given, so every answer below assumes the UNPINNED reading
  (global trace). The shipped DEFAULT partitions by principal, under which a rule
  reported live here may never fire.

agent-policy.dw against SupervisorApproval.tla: 7 rule(s)

  SupervisorApproval.tla COMPILED BUT DID NOT EVALUATE. TLC says:

      Error: The first argument of > should be an integer, but instead it is:
      Error: The error occurred when TLC was evaluating the nested

Nothing was checked. No claim was decided either way, so there is no verdict
about the policy here -- the module needs fixing first.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,891 | 5,892 | 11,783 | 44.1 |
| draft round 2 | 13,358 | 1,433 | 14,791 | 9.0 |
| draft round 3 | 20,521 | 5,029 | 25,550 | 23.7 |
| **3 model call(s)** | **39,770** | **12,354** | **52,124** | **76.7** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            88.9s
  preflight         0.0s
  score             3.1s
  report            0.0s
  total            92.2s
```

Of which 76.7s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
