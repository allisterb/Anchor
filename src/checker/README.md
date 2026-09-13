# `checker` — what follows from a policy

[`translator`](../translator) decides what a policy *says*. This decides what follows from it, by
asking TLC questions the policy text cannot answer about itself.

Also reachable as `anchor check`, which finds the interpreter and the Anchor tree itself and
passes the exit code straight through — see [`Anchor.CLI`](../Anchor.CLI).

```bash
python src/checker/properties.py tests/policies/docs_trading.dw
python src/checker/properties.py a.dw --against b.dw
python src/checker/properties.py firewall.dw --property firewall.tla
python src/checker/properties.py firewall.dw --describe    # what a --property module may name
python src/checker/properties.py big.dw --smoke 1000      # random walk, for a model too big to exhaust
```

## The smoke tier, and why its polarity is backwards from every other smoke test

`--smoke N` runs TLC as a random walk of N behaviours instead of exhausting the state space. The
usual reason to do that is a sound NEGATIVE: find a counterexample and the spec is broken, find none
and you have learnt nothing.

**Here it is the other way round.** This checker already reads TLC backwards -- a violation is the
GOOD outcome, the witness proving a rule does something. So a random walk gives a sound POSITIVE:

| smoke says | means | sound? |
|---|---|---|
| `live` | a witness was found, so the rule really does change a verdict | **yes** -- a witness is a witness however it was reached |
| `unknown` | this walk did not reach a session where the rule matters | it is **not a verdict**, and never means the rule is inert |

So a smoke run can report `live`, and **can never report VACUOUS, REDUNDANT or DEAD**. Those three
are claims of ABSENCE, a random walk cannot establish absence, and each of them tells someone to
delete a rule.

**What it is for is not speed on the cases exhaustive already handles.** Exhaustive search stops at
the first violation, so a live rule is found quickly either way. It is for models where exhaustive
does not finish at all -- which is exactly what raising `--attempts` to gain confidence in a VACUOUS
verdict produces. There, smoke turns "no answer about anything" into "these rules are definitely
live, and the rest I could not settle".

## Two kinds of property, and the difference is who can state it

| | |
|---|---|
| **derivable** | statable from the policy alone. We write these for you |
| **intentional** | only the author knows it. You write it, we check it |

### Derivable — the three that come in the box

| question | verdict | meaning |
|---|---|---|
| Can this permit ever grant? | **VACUOUS** | it never fires — whatever it was meant to allow is unreachable. A bug, not untidiness. |
| Is this rule load-bearing? | **REDUNDANT** | it fires, but another permit always would too. |
| | **DEAD** | this forbid never denies anything the rest of the set would have allowed. |
| Do two versions ever disagree? | `--against` | a session they decide differently, or a bounded no. |

They are one question underneath — *does deleting or changing this rule change some verdict* — and
every answer is either **a witness session** or **a bounded no**. The bound is printed with the
answer, because a bounded no is not a proof and should not read like one.

There is no fourth derivable check. Without being told what a policy is *for*, there is nothing
further to say about it.

### Intentional — `--property`

```bash
python src/checker/properties.py firewall.dw --property firewall.tla
```

A property module is TLA+ of your own extending the generated `PolicyUnderTest`, stating what the
policy is supposed to mean. It needs a companion `.cfg` naming its invariants — naming them is
deliberate, because a property nobody listed is a property nobody checked.

**One mechanism, not two.** `Vacuity.tla` is itself a property module extending the same generated
records; the only difference is that it explores sessions and a per-request claim does not.

#### Why the derivable checks are not enough

`firewall_open.dw` drops a `forbid` and widens a permit, letting the whole internet connect on port
22. The built-in checks do not miss it silently — they report

```
REDUNDANT permit #1   it fires, but another permit always would too
```

which is **true**, and whose advice — delete the redundant rule — shrinks the policy and leaves the
hole exactly where it was. The redundancy is a *symptom* of the over-broad permit, and a check that
cannot know what the policy was for cannot tell you which of the two rules is the mistake.

The property can, because it was told:

```
BROKEN  Invariant OutsideIsRefused is violated by the initial state:
        req = [port |-> [k |-> "n", v |-> 22], origin |-> [k |-> "s", v |-> "external"]]
```

#### State the requests your claim is about

`PolicyUnderTest` deliberately offers **no** `Inputs`. The request space derivable from a policy
comes from that policy's own literals, so a claim about a value it never mentions ranges over no
such request — it holds **vacuously** and reports success having looked at nothing.

That is not hypothetical: it is what the first version of `firewall.tla` did. Drop the `forbid` and
`"external"` leaves the vocabulary, so `OutsideIsRefused` passed against the broken policy. Two
lines fix it, and they belong to the claim:

```tla
Requests == {[port |-> Num(p), origin |-> Str(o)] : p \in {22, 2222}, o \in {"local", "external"}}
```

#### And that failure is now detected rather than described — `anchor explain`

The paragraph above is a warning that was only ever enforced by whoever read it. `explain` reads
the module instead, and says what each claim forbids and how many of the states it ranges over its
condition even applies to:

```bash
python src/checker/explain.py examples/aws1/TrustDecay10.tla
anchor check policy.dw --property TrustDecay10.tla --explain   # the same, before the verdict
```

```
  LosesWriteAfter10m
     says      whenever gap is greater than 10 * Minute (= 600), then the policy REFUSES it
     forbids   gap is greater than 10 * Minute (= 600), and yet the policy GRANTS it
     applies   to 3 of the 6: gap = 840, gap = 960, gap = 1800
```

`applies to NONE` is the vacuous claim above, caught before TLC starts, and it exits **4** — the
same code `--mutation-score` uses for the same defect found the expensive way.

**It runs no model checker**, which is the point: the checkpoint the literature puts at the
property-formulation boundary is only useful if it is instant. It is a small recursive-descent
reader over the fragment these modules state claims in, and it computes the state space and the
condition — ordinary arithmetic over values the module itself names. It does **not** evaluate
`Decide`; that is the whole authorization semantics, TLC is about to do it properly, and a second
implementation here would disagree silently.

So the two gates catch different things and neither replaces the other:

| | catches | costs |
|---|---|---|
| `explain` | a claim whose condition no state satisfies; one true by its own arithmetic; a `.cfg` naming an invariant that does not exist; claims defined but never listed | milliseconds, reading |
| `--mutation-score` | a claim that holds of the policy *and of every broken version of it* — including a tautology about the decision, which reading cannot see | one TLC run per mutant |

## The answer this must never get wrong

A false **VACUOUS** tells someone to delete a rule that works. Everything else the checker can get
wrong wastes a reader's time; that one changes their policy.

It has been got wrong twice, and both are pinned as fixtures rather than described:

- `tests/policies/string_output.dw` — every output field was modelled as boolean, so a gate on a
  string output could never match. Eight output binds in Dogwood's own corpus compare against a
  string.
- `tests/policies/like_impossible.dw` — where the checker cannot construct a value satisfying two
  `like` patterns at once, it **refuses** rather than reporting VACUOUS, because "no such string
  exists" and "the search was not clever enough" are indistinguishable from in here.

The rule that falls out: when this cannot decide, it refuses and names what is missing. A refusal
is a correct answer; a false VACUOUS is not.

## Why it is not part of `translator`

Translating a policy and reasoning about one are different jobs with different failure modes, and
the MCP server will want them separately — "what does this policy say" is a question you can answer
without ever starting a JVM.

The seam between them is `PolicyUnderTest.tla`, which [`translator/policy_module.py`](../translator/policy_module.py)
generates. Everything here extends it, and so does every property anyone writes.
