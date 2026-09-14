# 01-workflow-sequencing.dw

**Stated intention.** Any individual trade over $25,000 requires advisor approval, one approval per trade.

> **A budget cap fired during this run.**
>
> - draft round 1 was cut off by the limit_turns cap
> - draft round 3 was cut off by the limit_turns cap
>
> Raise `--turns` / `--total-tokens` / `--output-tokens`, or narrow the intention, and run it again.

*Drafted in 3 of 3 attempt(s), and the allowance ran out -- what follows is the last attempt, judged by the same gates as any other.*

## No property was checked: the draft was rejected at `preflight`

The gate below is a criterion in code, not a judgement a model was asked to make. Nothing downstream ran, and nothing here was verified.

- the draft did not contain both a module and a .cfg between the ===MODULE=== and ===CONFIG=== markers

---

*A property drafted by a model and gated by Anchor. Findings against an agent-authored property are weaker evidence than findings against one a person wrote.*
