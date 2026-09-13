# The questions, in plain language

What someone would actually ask about these policies, phrased the way they would actually ask it.
No TLA+ vocabulary, no mention of invariants or bounds or model checking — those are the tool's
problem, not the asker's.

[`transcript.md`](transcript.md) is the agent's answers to exactly these, with every tool call and
its full reply. Regenerate it with:

```bash
python src/agent/policy_agent.py examples/aws1/<policy>.dw --ask "<question>" \
    --transcript examples/aws1/transcript.md --heading "<title>"
```

---

### 1. Is this policy doing anything?

*Policy:* `03-data-freshness.dw`

> Is this policy actually doing anything, or is it dead weight? If some part of it can never
> apply, tell me which part and why.

The naive question, and the one a linter is expected to answer. Worth asking first because the
answer is not the obvious one: alone, this policy grants nothing at all.

---

### 2. Does it mean what its author said?

*Policy:* `07-trust-decay.dw`

> The person who wrote this policy says it means: "After 15 minutes without advisor interaction,
> the agent loses access to write operations." I have written that claim out formally at
> `examples/aws1/TrustDecay.tla`. Does the policy actually mean that? If not, show me a concrete
> situation where it does the wrong thing.

The question this whole project exists for. Nothing about the policy's text, its validation, or
the built-in checks can answer it — only a statement of intent, checked.

---

### 3. Would a tighter rule hold too?

*Policy:* `07-trust-decay.dw`

> Suppose I wanted the agent to lose write access after ten minutes rather than fifteen. Does this
> policy already give me that, or would I have to change it?

A different question from (2), and the distinction matters: "does it do what it says" and "does it
also do this other thing I want" have different answers and conflating them serves neither.

---

### 4. Do my two protections actually both apply?

*Policy:* `agent-policy.dw`

> This policy set is supposed to protect trades two ways: the profile being traded against must be
> one this session actually loaded, and the price must be less than 30 seconds old. I have written
> that out at `examples/aws1/TradeGate.tla`. Are both really required, or can a trade get through
> with only one of them satisfied?

The composition question. Each rule is fine; what they mean together is the thing nobody checked.

---

### 5. What did my edit change?

*Policies:* `agent-policy.dw` against `03-data-freshness.dw`

> I have two versions of this policy. Tell me whether the first one allows anything the second one
> does not, and show me a concrete example of it.

The everyday question, and the one that should come with every change.
