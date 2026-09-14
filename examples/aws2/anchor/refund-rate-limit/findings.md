# agent-policy.dw

**Stated intention.** The agent might attempt no more than three refunds against the same account within one hour.

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module did not compile, so nothing was checked:
no --event-schema given, so every answer below assumes the UNPINNED reading
  (global trace). The shipped DEFAULT partitions by principal, under which a rule
  reported live here may never fire.

agent-policy.dw against RefundRateLimit.tla: 7 rule(s)

  RefundRateLimit.tla COMPILED BUT DID NOT EVALUATE. TLC says:

      Error: The first argument of <= should be an integer, but instead it is:
      Error: The error occurred when TLC was evaluating the nested

Nothing was checked. No claim was decided either way, so there is no verdict
about the policy here -- the module needs fixing first.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 5,889 | 5,272 | 11,161 | 25.4 |
| **1 model call(s)** | **5,889** | **5,272** | **11,161** | **25.4** |

Time per stage, model calls and verification together:

```
  describe          0.1s
  draft            30.4s
  preflight         0.0s
  score             2.6s
  report            0.0s
  total            33.2s
```

Of which 25.4s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
