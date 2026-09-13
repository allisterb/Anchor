# Intents — what each policy is SUPPOSED to mean

The prose here is the **article's**, not ours and not the policy's. That is the whole point: a
property derived from a policy is a restatement of it, and checking a policy against its own
restatement always passes. Autoformalising a *requirement* is a different act, and only the first
can disagree with the rules.

Each intent below is quoted or paraphrased from
[the AWS article](https://aws.amazon.com/blogs/machine-learning/securing-ai-agents-with-temporal-policies-in-amazon-bedrock-agentcore/),
and each is repeated verbatim in its policy file's header comment so the provenance can be checked
against the transcription. **The drafter never sees either.** `describe` hands it the generated
vocabulary and nothing else; the intent reaches it only through `--intent`.

Consumed by `python src/agent/pipeline.py examples/aws1 --intents examples/aws1/intents.md`.

## 01-workflow-sequencing.dw

> A rebalance requires a portfolio load, which in turn requires a client profile to have been
> fetched, in that order.

## 02-output-to-input.dw

> The profile a trade is executed against must be the one this trajectory actually loaded — not
> merely that some profile was loaded at some point.

## 03-data-freshness.dw

> The agent cannot act on a stale quote: a trade must follow a recent market price.

## 04-cumulative-budget-cap.dw

> No single session can exceed $60,000 in total trade value.

## 05-human-approval.dw

> Any individual trade over $25,000 requires advisor approval, one approval per trade.

## 07-trust-decay.dw

> After 15 minutes without advisor interaction, the agent loses access to write operations.
