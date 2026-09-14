# Intents — what each policy is SUPPOSED to mean

The prose here is the **article's**, not ours and not the policy's, for the reason given in
[`../aws1/intents.md`](../aws1/intents.md): a property derived from a policy restates it, and a
policy checked against its own restatement always passes.

Every intent below is quoted **verbatim** from
[the AWS article](https://aws.amazon.com/blogs/machine-learning/authoring-dogwood-policies-from-natural-language-in-amazon-bedrock-agentcore/)
and repeated in its policy file's header comment, so the transcription can be checked. **The
drafter never sees either** — `describe` hands it the generated vocabulary and nothing else.

One of these is already known to be broken, and it is the reason this directory exists: policy 3
sums `::request`, so it caps *attempts* rather than *transfers*. Policy 4 is the same shape and is
correct, because its requirement says "attempt". A drafted property that catches the first and
clears the second is the outcome to look for.

Consumed by `anchor auto examples/aws2 --intents examples/aws2/intents.md`.

## 01-business-hours.dw

> Refunds might be issued only during business hours, defined as 9:00 AM-5:00 PM UTC, and only for
> amounts of $2,500 or less.

## 02-identity-verification.dw

> Do not initiate a transfer unless the caller's identity has been verified for that same account
> within the previous 15 minutes.

## 03-cumulative-cap.dw

> Block a transfer if the total amount transferred in the past 12 hours would exceed $50,000.

## 04-refund-rate-limit.dw

> The agent might attempt no more than three refunds against the same account within one hour.

## 06-supervisor-approval.dw

> A refund over $500 requires a supervisor approval for that charge within the previous 30 minutes.
