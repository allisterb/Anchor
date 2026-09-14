# agent-policy.dw

**Stated intention.** Refunds might be issued only during business hours, defined as 9:00 AM-5:00 PM UTC, and only for amounts of $2,500 or less.

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
no --event-schema given, so every answer below assumes the UNPINNED reading
  (global trace). The shipped DEFAULT partitions by principal, under which a rule
  reported live here may never fire.

agent-policy.dw against BusinessHours.tla: 7 rule(s)

  BusinessHours.tla COMPILED BUT DID NOT EVALUATE. TLC says:

      Error: The first argument of <= should be an integer, but instead it is:
      Error: The error occurred when TLC was evaluating the nested

Nothing was checked. No claim was decided either way, so there is no verdict
about the policy here -- the module needs fixing first.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,909 | 5,178 | 11,087 | 32.7 |
| **1 model call(s)** | **5,909** | **5,178** | **11,087** | **32.7** |

Time per stage, model calls and verification together:

```
  describe          0.2s
  draft            37.5s
  preflight         0.0s
  score             3.3s
  report            0.0s
  total            41.0s
```

Of which 32.7s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
