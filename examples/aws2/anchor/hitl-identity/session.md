# agent-policy.dw: a session

**What was first asked for.**

> Do not initiate a transfer unless the caller's identity has been verified for that same account within the previous 15 minutes.

**What the person was asked, and what they said.**

- *Name two things: one this policy must NEVER allow, and one it MUST allow -- a request that has met every condition and has to succeed.*
  > Must never be allowed: an initiate_transfer on account 1 with no successful verify_identity for that account in the previous 15 minutes. Must be allowed: an initiate_transfer on account 1 when verify_identity for account 1 returned verified = TRUE 60 seconds earlier.

| attempt | outcome | rounds | tokens | findings |
|---:|---|---:|---:|---|
| 1 | no property (rejected at score) | 2 | 144,939 | `attempt-1/findings.md` |
| 2 | property holds | 2 | 106,052 | `attempt-2/findings.md` |

**250,991 tokens** over 6 model call(s) in 2 attempt(s).

The last attempt passed every gate, and the person confirmed the plain-English reading of the claim before anything was checked.

---

*The property was drafted by a model and gated by Anchor. A person stated the requirement and confirmed a plain-English reading of the claim, which is better evidence than an unattended run and is still not a person having written the property.*
