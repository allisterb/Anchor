# agent-policy.dw

**Stated intention.** Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

The person was then asked about this requirement, and said:

  Q: Name two things: one this policy must NEVER allow, and one it MUST allow -- a request that has met every condition and has to succeed.
  A: Must never be allowed: an initiate_transfer on account 1 with no successful verify_identity for that account in the previous 15 minutes. Must be allowed: an initiate_transfer on account 1 when verify_identity for account 1 returned verified = TRUE 60 seconds earlier.

**A person was asked about this requirement 1 time(s), and the answers are part of it:**

- *Name two things: one this policy must NEVER allow, and one it MUST allow -- a request that has met every condition and has to succeed.* — Must never be allowed: an initiate_transfer on account 1 with no successful verify_identity for that account in the previous 15 minutes. Must be allowed: an initiate_transfer on account 1 when verify_identity for account 1 returned verified = TRUE 60 seconds earlier.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 2 of 3 attempt(s).*

## What was checked

`IdentityVerification.tla`, drafted from the intention above and kept because it caught 1 broken version(s) of this policy.

### Does it say what you asked for?

**A person was shown, in plain English, what this claim forbids, and confirmed it is what they meant — before anything was checked.** They did not read the formal claim, so what they confirmed is the reading of it; the two are generated from the same module and the reading is the part a person can audit.

A second model, shown only the requirement and the plain-English reading of the claim — never the formal claim itself — judged that they match. That is an agreement between two models, not a proof that the claim captures the requirement.

## Verdicts

```
Policy: agent-policy.dw
Property: IdentityVerification

The stated property HOLDS.

WHAT WAS ACTUALLY CHECKED -- each claim, what it forbids, and how many of the states it ranges over its condition applies to:

IdentityVerification

  2 claims will be checked, over 64 states.
  hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 1, gap = 60,
  hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 1, gap = 900,
  hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 1, gap = 901,
  hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 1, gap =
  1200, hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 2, gap
  = 60, hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 2, gap
  = 900, hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 2, gap
  = 901, hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount = 2, gap
  = 1200, and 56 more

  VerifiedTransferAllowed
      says      whenever hasVerification holds and verified holds and verifyAccount is
                transferAccount and gap is at most FifteenMinutes, then TransferAllowed holds
      forbids   hasVerification holds and verified holds and verifyAccount is transferAccount
                and gap is at most FifteenMinutes, and yet TransferAllowed does not hold
      applies   to 4 of the 64: hasVerification = TRUE, verifyAccount = 1, verified = TRUE,
                transferAccount = 1, gap = 60, hasVerification = TRUE, verifyAccount = 1,
                verified = TRUE, transferAccount = 1, gap = 900, hasVerification = TRUE,
                verifyAccount = 2, verified = TRUE, transferAccount = 2, gap = 60,
                hasVerification = TRUE, verifyAccount = 2, verified = TRUE, transferAccount =
                2, gap = 900

  UnverifiedTransferRefused
      says      whenever hasVerification does not hold or verified does not hold or
                verifyAccount is not transferAccount or gap is greater than FifteenMinutes,
                then TransferAllowed does not hold
      forbids   hasVerification does not hold or verified does not hold or verifyAccount is not
                transferAccount or gap is greater than FifteenMinutes, and yet TransferAllowed
                holds
      applies   to 60 of the 64: hasVerification = FALSE, verifyAccount = 1, verified = FALSE,
                transferAccount = 1, gap = 60, hasVerification = FALSE, verifyAccount = 1,
                verified = FALSE, transferAccount = 1, gap = 900, hasVerification = FALSE,
                verifyAccount = 1, verified = FALSE, transferAccount = 1, gap = 901,
                hasVerification = FALSE, verifyAccount = 1, verified = FALSE, transferAccount =
                1, gap = 1200, hasVerification = FALSE, verifyAccount = 1, verified = FALSE,
                transferAccount = 2, gap = 60, hasVerification = FALSE, verifyAccount = 1,
                verified = FALSE, transferAccount = 2, gap = 900, and 54 more

  Read the `forbids` lines before the run, not after it. Each one is the only
  thing its claim can catch; if none of them describes something you would
  object to, the check will pass without having tested what you meant.

This says nothing about requests the property does not name.

The derived questions were NOT attempted: this policy is outside the subset they can range over.
  REFUSED: agent-policy.dw is outside the modelled subset
  policy reads 6 input/output fields; the request space is the product of their domains, so this would explode (limit 4, raise with --max-fields)
That is a limit of those questions, not a verdict about the policy.
```

## Reported

### Verification Summary: `IdentityVerification` on `agent-policy.dw`

The property **`IdentityVerification` held** across the **64 specific states** evaluated by the model checker.

---

### What Was Checked and What Held

The check tested 2 claims over a bounded state space of 64 discrete combinations:
* **`hasVerification`**: `{TRUE, FALSE}`
* **`verified`**: `{TRUE, FALSE}`
* **`verifyAccount`**: `{1, 2}`
* **`transferAccount`**: `{1, 2}`
* **`gap`**: `{60, 900, 901, 1200}` seconds (where 15 minutes = 900 seconds)

#### 1. `VerifiedTransferAllowed` (Held)
* **Rule checked**: If verification was attempted (`hasVerification = TRUE`), succeeded (`verified = TRUE`), the accounts match (`verifyAccount = transferAccount`), and the time elapsed is within 15 minutes (`gap` $\le$ 900s), `TransferAllowed` must hold.
* **Scope**: Applied to and passed on **4 of the 64 states** (combinations where accounts were both 1 or both 2, and gap was 60s or 900s).

#### 2. `UnverifiedTransferRefused` (Held)
* **Rule checked**: If verification is missing, failed, the verified account does not match the transfer account, or the time elapsed exceeds 15 minutes (`gap` > 900s), `TransferAllowed` must not hold.
* **Scope**: Applied to and passed on **60 of the 64 states**.

---

### What Was Not Checked

* **Unchecked parameter values**: 
  * Any account identifiers other than `1` and `2`.
  * Any time gap values other than `60`, `900`, `901`, and `1200` seconds.
* **Derived questions**: Automated derived checks were **not run** (refused by the model checker because the policy references 6 input/output fields, exceeding the tool's default 4-field limit).

---

*A property drafted by a model and gated by Anchor. A person stated the requirement and confirmed a plain-English reading of the claim, which is better evidence than an unattended run and is still not a person having written the property.*

## What this run cost

| | tokens in | of which cached | out | total | seconds |
|---|---:|---:|---:|---:|---:|
| draft round 1 (cut off) | 82,181 | 39,819 | 4,107 | 86,288 | 62.0 |
| draft round 2 | 15,111 | 11,949 | 563 | 15,674 | 5.4 |
| the review | 1,164 | 0 | 381 | 1,545 | 4.6 |
| the report | 1,203 | 0 | 1,342 | 2,545 | 10.4 |
| **4 model call(s)** | **99,659** | **51,768** | **6,393** | **106,052** | **82.3** |

Time per stage, model calls and verification together:

```
  describe          0.0s
  draft            75.2s
  preflight         0.0s
  score            18.6s
  review            4.6s
  confirm          20.4s
  check             0.2s
  answer           10.4s
  report            0.0s
  total           129.4s
```

Of which 82.3s was model calls; the rest is verification -- TLC runs in `score` and `check`, which cost no tokens.
