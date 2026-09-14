# agent-policy.dw: a session

**What was first asked for.**

> A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.

**What the person was asked, and what they said.**

- *Name one thing this policy must NEVER allow. If somebody broke it, what would you see go wrong?*
  > An issue_refund of 2500 on charge_id 1 must be refused when there is no approved request_approval for that same charge_id in the previous 30 minutes. It must still be refused if the approval was for a different charge_id, or if it happened more than 30 minutes before the refund.

| attempt | outcome | rounds | tokens | findings |
|---:|---|---:|---:|---|
| 1 | no property (rejected at score) | 2 | 29,788 | `attempt-1/findings.md` |
| 2 | property holds | 1 | 17,349 | `attempt-2/findings.md` |

**47,137 tokens** over 5 model call(s) in 2 attempt(s).

The last attempt passed every gate, and the person confirmed the plain-English reading of the claim before anything was checked.

---

*The property was drafted by a model and gated by Anchor. A person stated the requirement and confirmed a plain-English reading of the claim, which is better evidence than an unattended run and is still not a person having written the property.*
