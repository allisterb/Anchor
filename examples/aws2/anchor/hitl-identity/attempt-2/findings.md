# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

The person was then asked about this requirement, and said:

  Q: Name two things: one this policy must NEVER allow, and one it MUST allow -- a request that has met every condition and has to succeed.
  A: Must never be allowed: an initiate_transfer on account 1 with no successful verify_identity for that account in the previous 15 minutes. Must be allowed: an initiate_transfer on account 1 when verify_identity for account 1 returned verified = TRUE 60 seconds earlier.

**A person was asked about this requirement 1 time(s), and the answers are part of it:**

- *Name two things: one this policy must NEVER allow, and one it MUST allow -- a request that has met every condition and has to succeed.* — Must never be allowed: an initiate_transfer on account 1 with no successful verify_identity for that account in the previous 15 minutes. Must be allowed: an initiate_transfer on account 1 when verify_identity for account 1 returned verified = TRUE 60 seconds earlier.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `score`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the module compiled but could not be evaluated, so nothing was checked:
  IdentityVerification.tla COMPILED BUT DID NOT EVALUATE. TLC says:

      Error: Attempted to check equality of integer 1 with non-integer:
      Error: TLC was unable to fingerprint.

Nothing was checked. No claim was decided either way, so there is no verdict
about the policy here -- the module needs fixing first.

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 | 6,687 | 0 | 3,673 | 10,360 | 23.0 |
| draft round 2 | 10,696 | 4,074 | 21,795 | 32,491 | 122.6 |
| draft round 3 | 32,827 | 8,173 | 12,920 | 45,747 | 79.1 |
| **3 model call(s)** | **50,210** | **12,247** | **38,388** | **88,598** | **224.7** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft           235.1s
  preflight         0.0s
  score             2.5s
  report            0.0s
  total           237.6s
```

Of which 224.7s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
