# agent-policy.dw

**Stated intention.** A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

The person was then asked about this requirement, and said:

  Q: Name one thing this policy must NEVER allow. If somebody broke it, what would you see go wrong?
  A: An issue_refund of 2500 on charge_id 1 must be refused when there is no approved request_approval for that same charge_id in the previous 30 minutes. It must still be refused if the approval was for a different charge_id, or if it happened more than 30 minutes before the refund.

**A person was asked about this requirement 1 time(s), and the answers are part of it:**

- *Name one thing this policy must NEVER allow. If somebody broke it, what would you see go wrong?* — An issue_refund of 2500 on charge_id 1 must be refused when there is no approved request_approval for that same charge_id in the previous 30 minutes. It must still be refused if the approval was for a different charge_id, or if it happened more than 30 minutes before the refund.

## No property was checked: the draft was rejected at `review`

The gate below is a second model's judgement about whether the claim says what the requirement says. It has no oracle behind it, and it is the one gate here a person may overrule. Nothing downstream ran, and nothing here was verified.

- a second model, shown only the requirement and the plain-English reading of the claim, judged that they do not match:

VERDICT: MISMATCH

The formal claim only examines fixed hardcoded amounts ($2500 and $500) rather than checking the policy for arbitrary amounts over $500. Additionally, `RefundUnder500Permitted` only tests an amount equal to $500, failing to capture general refunds under the threshold.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | out | total | seconds |
|---|---:|---:|---:|---:|
| draft round 1 | 6,602 | 6,219 | 12,821 | 39.8 |
| the review | 721 | 446 | 1,167 | 5.8 |
| **2 model call(s)** | **7,323** | **6,665** | **13,988** | **45.6** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft            49.8s
  preflight         0.0s
  score            21.0s
  review            5.8s
  report            0.0s
  total            76.7s
```

Of which 45.6s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
