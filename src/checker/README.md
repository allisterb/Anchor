# `checker` — what follows from a policy

[`translator`](../translator) decides what a policy *says*. This decides what follows from it, by
asking TLC questions the policy text cannot answer about itself.

```bash
python src/checker/vacuity.py tests/policies/docs_trading.dw
python src/checker/vacuity.py a.dw --against b.dw
```

| question | verdict | meaning |
|---|---|---|
| Can this permit ever grant? | **VACUOUS** | it never fires — whatever it was meant to allow is unreachable. A bug, not untidiness. |
| Is this rule load-bearing? | **REDUNDANT** | it fires, but another permit always would too. |
| | **DEAD** | this forbid never denies anything the rest of the set would have allowed. |
| Do two versions ever disagree? | `--against` | a session they decide differently, or a bounded no. |

They are one question underneath — *does deleting or changing this rule change some verdict* — and
every answer is either **a witness session** or **a bounded no**. The bound is printed with the
answer, because a bounded no is not a proof and should not read like one.

## The answer this must never get wrong

A false **VACUOUS** tells someone to delete a rule that works. Everything else the checker can get
wrong wastes a reader's time; that one changes their policy.

It has been got wrong twice, and both are pinned as fixtures rather than described:

- `tests/policies/string_output.dw` — every output field was modelled as boolean, so a gate on a
  string output could never match. Eight output binds in Dogwood's own corpus compare against a
  string.
- `tests/policies/like_impossible.dw` — the newer half of the same lesson. Where the checker cannot
  construct a value satisfying two `like` patterns at once, it **refuses** rather than reporting
  VACUOUS, because "no such string exists" and "the search was not clever enough" are
  indistinguishable from in here.

The rule that falls out: when this cannot decide, it refuses and names what is missing. A refusal
is a correct answer; a false VACUOUS is not.

## Why it is not part of `translator`

Translating a policy and reasoning about one are different jobs with different failure modes, and
the MCP server will want them separately — "what does this policy say" is a question you can answer
without ever starting a JVM.

It did live in `tests/strands/` for a while, which was wrong in the plainer way: it is the tool,
not a test of the tool.
