# Agent transcript

*Generated 2026-09-13 07:08 UTC by `src/agent/policy_agent.py --transcript`. Tool calls and their full replies are included: the prose is a claim, and the tool output is the evidence for it.*

## 1. Is this policy doing anything?

**Asked:**

> Is this policy actually doing anything, or is it dead weight? If some part of it can never apply, tell me which part and why.
> 
> The policy file is examples\aws1\03-data-freshness.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `ListKnowledge`

```json
{"search": "verdicts"}
```

<details><summary>tool result (success)</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","description":"What VACUOUS, REDUNDANT, DEAD, live and unknown mean, and what each one does not mean.","uri":"anchor://knowledge/reading-verdicts"}]
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

**Tool call 3** — `CheckPolicy`

```json
{"policy": "examples\\aws1\\03-data-freshness.dw"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[{"rule":1,"effect":"permit","verdict":"VACUOUS","note":"no session of up to 3 attempts makes it grant"}],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). The shipped DEFAULT partitions by principal, under which a rule\r\n  reported live here may never fire.\r\n\r\n03-data-freshness.dw: 1 permit(s), 0 forbid(s), bound 3 attempts\r\n\r\n  permit #1  action == execute_trade VACUOUS   no session of up to 3 attempts makes it grant\r\n      because: formerly within 30s get_market_price::response\r\n\r\nVACUOUS permit #1\r\n\r\nA rule that changes no verdict can be deleted, and a policy set is easier to reason\r\nabout the fewer of them it has.\r\n  VACUOUS    the permit never fires at all -- whatever it was meant to\r\n             allow is unreachable, a bug rather than untidiness\r\n","exitCode":0,"propertyBroken":false,"inert":[{"rule":1,"effect":"permit","verdict":"VACUOUS","note":"no session of up to 3 attempts makes it grant"}],"unsettled":[]}
```

</details>

The policy `examples\aws1\03-data-freshness.dw` contains one rule, and it has been found to be **VACUOUS**.

This means that `permit #1`,

which is `action == execute_trade`, never grants anything in any session of up to 3 attempts. Whatever this rule was intended to allow is currently unreachable. This is considered a bug.

The reason for its inertness is: `formerly within 30s get_market_price::response`.

This analysis was performed under the **UNPINNED reading**, as no event schema was provided. This means that the model assumes a global trace of events. The shipped default for Dogwood policies partitions history by principal, and a rule found to be live under the unpinned reading might not fire under the default deployed reading.

## 2. Does it mean what its author said?

**Asked:**

> The person who wrote this policy says it means: "After 15 minutes without advisor interaction, the agent loses access to write operations." I have written that claim out formally at `examples/aws1/TrustDecay.tla`. Does the policy actually mean that? If not, show me a concrete situation where it does the wrong thing.
> 
> The policy file is examples\aws1\07-trust-decay.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `CheckPolicy`

```json
{"policy": "examples/aws1/07-trust-decay.dw", "property": "examples/aws1/TrustDecay.tla"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). The shipped DEFAULT partitions by principal, under which a rule\r\n  reported live here may never fire.\r\n\r\n07-trust-decay.dw against TrustDecay.tla: 1 rule(s)\r\n\r\n  BROKEN  Invariant KeepsWriteWhileAdvisorEngaged is violated by the initial state:\r\n      gap = 1\r\n        \\* The other half, which the sentence implies and which is the part that makes the policy useful:\r\n        \\* while the advisor IS engaged, the agent can still work.\r\n        KeepsWriteWhileAdvisorEngaged ==\r\n            (gap \u003C= 15 * Minute) =\u003E TradeAllowed(gap)\r\n\r\nThe policy does not mean what the property says it means. The state above is the\r\nrequest that breaks the claim, and the claim is quoted beneath it -- read the two\r\ntogether, because a violated invariant says which direction failed only when you can\r\nsee what it asserted.\r\n","exitCode":1,"propertyBroken":true,"inert":[],"unsettled":[]}
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

No, the policy does not mean "After 15 minutes without advisor interaction, the agent loses access to write operations."

The tool found that the policy violates your formal claim `examples/aws1/TrustDecay.tla`.

**

Concrete situation where it does the wrong thing:**

The policy fails to allow write operations when the time since the last advisor interaction (`gap`) is 1 minute. According to your claim, write operations should be allowed when `gap` is less than or equal to 15 minutes. However, the model check shows that when `gap = 1`, the `TradeAllowed` condition is false, meaning write operations are *not* permitted.

This check was performed assuming an **UNPINNED reading** (global trace) because no event schema was provided. The shipped default partitions history by principal, under which the policy's behavior might differ.

## 3. Would a tighter rule hold too?

**Asked:**

> Suppose I wanted the agent to lose write access after ten minutes rather than fifteen. Does this policy already give me that, or would I have to change it?
> 
> The policy file is examples\aws1\07-trust-decay.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `DescribePolicyModule`

```json
{"policy": "examples\\aws1\\07-trust-decay.dw"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"module":{"source":"07-trust-decay.dw","reading":"no --event-schema given, so every answer below assumes the UNPINNED reading\n  (global trace). The shipped DEFAULT partitions by principal, under which a rule\n  reported live here may never fire.","module":"PolicyUnderTest","actions":["execute_trade","interact_advisor"],"kinds":["request","response"],"decisionKind":"request","inputFields":[],"outputFields":[],"pinKeys":[],"rules":[{"index":1,"effect":"permit","actions":["execute_trade"]}],"operators":{"Request(action, input)":"one request as the evaluator reads it","Policies":"the rule set, as the sequence Decide evaluates","AllValues":"every value any field may take -- Decide\u0027s last argument","InputDomain":"[field |-\u003E {values}] for the fields above","OutputDomain":"[field |-\u003E {values}] for the output fields","PinKeys":"the fields a universal pin partitions on; empty means global-trace"},"constructors":{"Str(x)":"a string","Num(x)":"an integer","Bool(x)":"TRUE or FALSE","Addr(a, b, c, d)":"an address, FOUR OCTETS -- TLC works in Java ints, so 208.4.4.0 as 3489924096 is not a value it can hold","Anon":"the anonymous principal/resource/session a per-request claim uses"},"rules_for_writing_one":["EXTENDS PolicyUnderTest, and instantiate DogwoodSemantics with Cases \u003C- \u003C\u003C \u003E\u003E.","Scalars are TAGGED. Write Num(22), never 22 -- TLC refuses a cross-kind comparison rather than quietly answering one.","There is no Inputs. State the requests your claim is about, including values this policy never mentions, or the claim may range over nothing and pass.","The .cfg must name SPECIFICATION Spec and every INVARIANT. A property nobody listed is a property nobody checked."],"skeleton":"---------------------------- MODULE P_07_trust_decay ----------------------------\n\\* What 07-trust-decay.dw is SUPPOSED to mean, stated by its author. The three built-in findings\n\\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the\n\\* other kind, and only the author can write it.\n\\*\n\\* SAVE THIS AS P_07_trust_decay.tla -- TLA\u002B requires the file name to match the module name, and a\n\\* module name may not contain \u0060-\u0060 or \u0060.\u0060 or begin with a digit, so it is not always the policy\u0027s\n\\* own name.\n\\*\n\\* Check it with:  python src/checker/properties.py 07-trust-decay.dw --property P_07_trust_decay.tla\nEXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest\n\nD == INSTANCE DogwoodSemantics WITH Cases \u003C- \u003C\u003C \u003E\u003E\n\n\\* The verdict for one request. No session: \u0022what does this policy decide for this request\u0022 is\n\\* not a temporal question, so there is no state machine beyond holding one request still.\nGrants(input) == D!Decide(\u003C\u003CRequest(\u0022execute_trade\u0022, input)\u003E\u003E, Policies, 1, AllValues)\n\n(***************************************************************************)\n(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)\n(*                                                                         *)\n(* Written out rather than derived from InputDomain, and that is the       *)\n(* point. A space derived from the policy\u0027s own literals cannot test a     *)\n(* claim about a value the policy never mentions: delete the rule that     *)\n(* names a value and it vanishes from the vocabulary, so the claim ranges  *)\n(* over nothing and PASSES having looked at nothing.                       *)\n(*                                                                         *)\n(* Add the values your claim is about, including ones this policy never    *)\n(* mentions.                                                               *)\n(***************************************************************************)\n\\* This policy reads no input fields, so one request is the whole space.\nRequests == {[f \\in {} |-\u003E Str(\u0022\u0022)]}\n\n\\* One request, chosen nondeterministically and held, so a violation\u0027s counterexample NAMES the\n\\* request that breaks the claim rather than merely reporting that one exists.\nVARIABLE req\nInit == req \\in Requests\nNext == UNCHANGED req\nSpec == Init /\\ [][Next]_req\n\n(***************************************************************************)\n(* THE CLAIM.                                                              *)\n(***************************************************************************)\nEverythingIsGranted == Grants(req)\n\n=============================================================================\n","config":"SPECIFICATION Spec\n\n\\* Naming the claims is deliberate. A property nobody listed is a property\n\\* nobody checked.\nINVARIANT EverythingIsGranted\n"}}
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["the-modelled-subset"]}
```

<details><summary>tool result (success)</summary>

```
[{"name":"the-modelled-subset","title":"The modelled subset, and why a refusal is not a failure","uri":"anchor://knowledge/the-modelled-subset","content":"# The modelled subset\n\nAnchor translates Dogwood policy text into TLA\u002B records that a validated evaluator checks. It\nmodels a **subset** of the language. When a policy uses something outside it, the checker refuses:\n\n\u0060\u0060\u0060\nREFUSED: like_impossible.dw is outside the modelled subset\n  input.stock is constrained by 2 \u0060like\u0060 patterns at once and no value satisfying all of\n  them could be constructed; deciding that needs glob intersection, which is not modelled\n\u0060\u0060\u0060\n\n**A refusal is a deliberate answer, not a breakdown.** The alternative \u2014 translating approximately\nand reporting a verdict anyway \u2014 produces a verdict nobody can attribute: you could not tell whether\n\u0060VACUOUS\u0060 described the policy or the approximation. So the house rule is to refuse rather than\napproximate, and refusals name the construct so they are actionable.\n\n\u0060Answered: false\u0060 with an empty finding list therefore means **no verdict was produced**. It does\nnot mean \u0022no problems found\u0022. Never summarise it as a clean result.\n\n## What is modelled\n\n- \u0060permit\u0060 / \u0060forbid\u0060, with forbid-overriding-permit and default-deny\n- action sets and scope binds, including wildcard (\u0060_\u0060) and fresh variables\n- Cedar-level conditions: comparison, \u0060\u0026\u0026\u0060, \u0060||\u0060, \u0060!\u0060, parentheses\n- temporal terms: \u0060formerly within \u003Cduration\u003E\u0060, aggregates, \u0060exists\u0060 with an entity-typed binder\n- \u0060like\u0060 patterns (glob), \u0060ip()\u0060 and \u0060isInRange\u0060 over IPv4, decimals, macros\n- event schemas: universal and partial pins, \u0060max_window\u0060\n\n## Common reasons for a refusal\n\n| refusal | why |\n|---|---|\n| window exceeds \u0060max_window\u0060 | the gateway\u0027s validator would reject the policy \u2014 see \u0060event-schemas-and-pins\u0060 |\n| two \u0060like\u0060 patterns on one field with no constructible joint witness | deciding it needs glob intersection |\n| ordering compared against a non-integer | ordering is modelled for **integers only**; the engine denies on decimals |\n| IPv6 address | not modelled |\n| more than \u0060maxFields\u0060 input/output fields | the request space is the product of their domains, so it would explode |\n| event kinds outside AgentCore\u0027s convention | the model only knows \u0060request\u0060 / \u0060response\u0060 / \u0060error\u0060 |\n| mixed value kinds on one field | scalars are tagged, and a cross-kind comparison is refused rather than silently answered |\n\n## What to do with a refusal\n\nRead the reason \u2014 it names the construct. Then either simplify the policy to stay inside the subset,\nor tell the user plainly that this policy cannot be checked and which construct is responsible. Do\nnot retry the same call, and do not fall back to reasoning about the policy yourself and presenting\nit as a checked result.\n\n## Two limits worth knowing separately\n\n- **Integers only for ordering.** \u0060\u003E\u0060, \u0060\u003C\u0060, \u0060\u003E=\u0060, \u0060\u003C=\u0060 are modelled for integers. Decimals are\n  excluded deliberately, because the reference engine denies on them.\n- **Addresses are four octets, never a 32-bit number.** TLC works in Java ints and stops at\n  2,147,483,647, so an address above 127.255.255.255 is not a value it can hold as an integer.\n"}]
```

</details>

Based on the analysis of `examples\\aws1\\07-trust-decay.dw`:

The policy does not define any input fields that could represent time or duration. This means the policy itself cannot track or respond to elapsed

time. Therefore, it cannot enforce a ten-minute write access limit, nor a fifteen-minute one.

To implement such a time-based restriction, the policy would need to be changed to incorporate a mechanism for tracking and evaluating time.

## 4. Do my two protections actually both apply?

**Asked:**

> This policy set is supposed to protect trades two ways: the profile being traded against must be one this session actually loaded, and the price must be less than 30 seconds old. I have written that out at `examples/aws1/TradeGate.tla`. Are both really required, or can a trade get through with only one of them satisfied?
> 
> The policy file is examples\aws1\agent-policy.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `CheckPolicy`

```json
{"policy": "examples/aws1/agent-policy.dw", "property": "examples/aws1/TradeGate.tla"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). The shipped DEFAULT partitions by principal, under which a rule\r\n  reported live here may never fire.\r\n\r\nagent-policy.dw against TradeGate.tla: 7 rule(s)\r\n\r\n  BROKEN  Invariant FreshPriceAloneIsNotEnough is violated by the initial state:\r\n      prereq = \u0022freshPriceOnly\u0022\r\n        FreshPriceAloneIsNotEnough ==\r\n            (prereq = \u0022freshPriceOnly\u0022) =\u003E ~Allowed(prereq)\r\n\r\nThe policy does not mean what the property says it means. The state above is the\r\nrequest that breaks the claim, and the claim is quoted beneath it -- read the two\r\ntogether, because a violated invariant says which direction failed only when you can\r\nsee what it asserted.\r\n","exitCode":1,"propertyBroken":true,"inert":[],"unsettled":[]}
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

The policy, as checked against `examples/aws1/

TradeGate.tla`, indicates that a trade can get through with only one of the conditions satisfied.

Specifically, the invariant `FreshPriceAloneIsNotEnough` was violated. This invariant claimed that if the `prereq` (pre-requisite) was "freshPriceOnly", then a trade should *not* be allowed. However, the model checker found a scenario where `prereq = "freshPriceOnly"` *was* allowed.

This means that having a fresh price alone is sufficient for a trade to be allowed by the policy, even without the profile being loaded.

The check was performed under the UNPINNED reading (global trace) because no event schema was provided. Under the shipped default (which partitions by principal), a rule reported live here may never fire.

## 5. What did my edit change?

**Asked:**

> I have two versions of this policy. Tell me whether the first one allows anything the second one does not, and show me a concrete example of it.
> 
> The policy file is examples\aws1\agent-policy.dw.
> 
> The second policy file, to compare against, is examples\aws1\03-data-freshness.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `CheckPolicy`

```json
{"against": "examples\\aws1\\03-data-freshness.dw", "policy": "examples\\aws1\\agent-policy.dw"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). The shipped DEFAULT partitions by principal, under which a rule\r\n  reported live here may never fire.\r\n\r\nagent-policy.dw vs 03-data-freshness.dw: 7 rule(s) vs 1, bound 3 attempts\r\n\r\n  MORE PERMISSIVE   this edit ADDS permissions\r\n\r\n  ADDED     a session this policy permits and the old one denies:\r\n\r\n              1. get_client_profile(profile_id = 1)  allowed   \u003C- 03-data-freshness.dw DENIES this\r\n\r\n            This is the direction worth reading twice -- it is what the edit\r\n            grants that nobody asked it to grant.\r\n\r\n--json gives the witness as structured events rather than this summary, and\r\n--keep DIR writes the model, the .cfg and the raw TLC output for re-running.\r\n\r\nBOUNDED. Sessions of up to 3 attempts, and the comparison is driven\r\nalong histories the NEW set produces -- sound because the two agree up to the first\r\npoint they disagree, which is the point this reports. A difference appearing only in\r\nlonger sessions is not excluded by this run.\r\n","exitCode":0,"propertyBroken":false,"inert":[],"unsettled":[]}
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

The policy `examples\aws1\agent-policy.dw` is

**MORE PERMISSIVE** than `examples\aws1\03-data-freshness.dw`. This means the first policy allows sessions that the second one would have denied.

A concrete example of a session permitted by `examples\aws1\agent-policy.dw` but denied by `examples\aws1\03-data-freshness.dw` is:

1.  `get_client_profile(profile_id = 1)`

This finding is bounded to sessions of up to 3 attempts.

Please note that this analysis was performed assuming the **UNPINNED reading** (a global trace) because no event schema was provided. The shipped default reading partitions history by principal, under which a rule reported as live here might never fire.

## 1. Is this policy doing anything?

**Asked:**

> Is this policy actually doing anything, or is it dead weight? If some part of it can never apply, tell me which part and why.
> 
> The policy file is examples\aws1\03-data-freshness.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `ListKnowledge`

```json
{"search": "verdict"}
```

<details><summary>tool result (success)</summary>

```
[{"name":"event-schemas-and-pins","title":"Event schemas and pins","description":"Why passing a .dwschema changes what a policy MEANS, not merely what is checked.","uri":"anchor://knowledge/event-schemas-and-pins"},{"name":"reading-verdicts","title":"Reading a verdict","description":"What VACUOUS, REDUNDANT, DEAD, live and unknown mean, and what each one does not mean.","uri":"anchor://knowledge/reading-verdicts"},{"name":"smoke-vs-exhaustive","title":"Smoke versus exhaustive","description":"What a random walk can and cannot settle here \u2014 and why the polarity is backwards from every other smoke test.","uri":"anchor://knowledge/smoke-vs-exhaustive"},{"name":"the-modelled-subset","title":"The modelled subset, and why a refusal is not a failure","description":"What Anchor will and will not translate, and why it refuses rather than approximating.","uri":"anchor://knowledge/the-modelled-subset"},{"name":"what-anchor-does-not-check","title":"What Anchor does not check","description":"The limits to state alongside any verdict, so a bounded answer is not reported as a proof.","uri":"anchor://knowledge/what-anchor-does-not-check"},{"name":"writing-a-property-module","title":"Writing a property module","description":"How to state what a policy is SUPPOSED to mean, and the trap that makes such a claim pass having checked nothing.","uri":"anchor://knowledge/writing-a-property-module"}]
```

</details>

**Tool call 2** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

**Tool call 3** — `CheckPolicy`

```json
{"policy": "examples\\aws1\\03-data-freshness.dw"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[{"rule":1,"effect":"permit","verdict":"VACUOUS","note":"no session of up to 3 attempts makes it grant"}],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). DOGWOOD\u0027S OWN DEFAULT IS THE OPPOSITE: it pins callerPrincipal\r\n  on every kind, so a deployed rule sees only its own principal\u0027s events and one\r\n  reported live here may never fire. Pass --pinned to check that reading, or\r\n  --event-schema for a real one.\r\n\r\n03-data-freshness.dw: 1 permit(s), 0 forbid(s), bound 3 attempts\r\n\r\n  permit #1  action == execute_trade VACUOUS   no session of up to 3 attempts makes it grant\r\n      because: formerly within 30s get_market_price::response\r\n\r\nVACUOUS permit #1\r\n\r\nA rule that changes no verdict can be deleted, and a policy set is easier to reason\r\nabout the fewer of them it has.\r\n  VACUOUS    the permit never fires at all -- whatever it was meant to\r\n             allow is unreachable, a bug rather than untidiness\r\n","exitCode":0,"propertyBroken":false,"inert":[{"rule":1,"effect":"permit","verdict":"VACUOUS","note":"no session of up to 3 attempts makes it grant"}],"unsettled":[]}
```

</details>

The policy `examples\aws1\03-data-freshness.dw` was checked using the UN

PINNED reading, meaning a global trace where all events are considered together. Note that Dogwood's default behavior is to partition history by principal; a rule found live under the unpinned reading might not fire in a deployed scenario.

The check found one rule to be `VACUOUS`:

*   **Rule 1 (permit):** This rule is `VACUOUS`, meaning it never grants anything in any session within 3 attempts. This suggests a bug in the policy, as whatever this rule was intended to allow is currently unreachable. The specific reason given is `because: formerly within 30s get_market_price::response`.

In summary, the policy, as checked, is effectively "dead weight" because its single permit rule is `VACUOUS`. This means that under the conditions of the check (unpinned reading, up to 3 attempts), this rule will never lead to a successful permit. You should investigate why the condition `formerly within 30s get_market_price::response` is preventing the rule from ever granting access, as this is likely an unintended behavior.

## 2. Does it mean what its author said?

**Asked:**

> The person who wrote this policy says it means: "After 15 minutes without advisor interaction, the agent loses access to write operations." I have written that claim out formally at `examples/aws1/TrustDecay.tla`. Does the policy actually mean that? If not, show me a concrete situation where it does the wrong thing.
> 
> The policy file is examples\aws1\07-trust-decay.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `ExplainPropertyModule`

```json
{"property": "examples/aws1/TrustDecay.tla"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"explanation":{"module":"TrustDecay.tla","states":["gap = 1","gap = 300","gap = 600","gap = 840","gap = 960","gap = 1800"],"scope":"read from Init","claims":[{"name":"LosesWriteAfter15m","defined":true,"says":"whenever gap is greater than 15 * Minute (= 900), then the policy REFUSES it (TradeAllowed(gap))","forbids":"gap is greater than 15 * Minute (= 900), and yet the policy GRANTS it (TradeAllowed(gap))","condition":"gap \u003E 15 * Minute","appliesTo":["gap = 960","gap = 1800"],"states":6,"unknownIn":0,"settledWithoutThePolicy":4,"falseWithoutThePolicy":[],"vacuous":false,"notes":[]},{"name":"KeepsWriteWhileAdvisorEngaged","defined":true,"says":"whenever gap is at most 15 * Minute (= 900), then the policy GRANTS it (TradeAllowed(gap))","forbids":"gap is at most 15 * Minute (= 900), and yet the policy REFUSES it (TradeAllowed(gap))","condition":"gap \u003C= 15 * Minute","appliesTo":["gap = 1","gap = 300","gap = 600","gap = 840"],"states":6,"unknownIn":0,"settledWithoutThePolicy":2,"falseWithoutThePolicy":[],"vacuous":false,"notes":[]},{"name":"LosesWriteAfter10m","defined":true,"says":"whenever gap is greater than 10 * Minute (= 600), then the policy REFUSES it (TradeAllowed(gap))","forbids":"gap is greater than 10 * Minute (= 600), and yet the policy GRANTS it (TradeAllowed(gap))","condition":"gap \u003E 10 * Minute","appliesTo":["gap = 840","gap = 960","gap = 1800"],"states":6,"unknownIn":0,"settledWithoutThePolicy":3,"falseWithoutThePolicy":[],"vacuous":false,"notes":[]}],"definedButNotChecked":[],"vacuous":[]}}
```

</details>

The policy at `examples/aws1/07-trust-decay.dw` makes several claims, as expressed in `examples/aws1/TrustDecay.tla`. These claims are checked under a session length bound of

5 attempts.

The claims are:
*   `LosesWriteAfter15m`: "whenever `gap` is greater than 15 minutes (900 seconds), then the policy REFUSES write operations (`TradeAllowed(gap)`)." It forbids `gap` being greater than 900 seconds, and yet the policy GRANTS it.
*   `KeepsWriteWhileAdvisorEngaged`: "whenever `gap` is at most 15 minutes (900 seconds), then the policy GRANTS write operations (`TradeAllowed(gap)`)." It forbids `gap` being at most 900 seconds, and yet the policy REFUSES it.
*   `LosesWriteAfter10m`: "whenever `gap` is greater than 10 minutes (600 seconds), then the policy REFUSES write operations (`TradeAllowed(gap)`)." It forbids `gap` being greater than 600 seconds, and yet the policy GRANTS it.

Now, let's check the policy against these claims.

**Tool call 2** — `CheckPolicy`

```json
{
  "attempts": 5,
  "policy": "examples/aws1/07-trust-decay.dw",
  "property": "examples/aws1/TrustDecay.tla",
  "witness": true
}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). DOGWOOD\u0027S OWN DEFAULT IS THE OPPOSITE: it pins callerPrincipal\r\n  on every kind, so a deployed rule sees only its own principal\u0027s events and one\r\n  reported live here may never fire. Pass --pinned to check that reading, or\r\n  --event-schema for a real one.\r\n\r\n07-trust-decay.dw against TrustDecay.tla: 1 rule(s)\r\n\r\n  BROKEN  Invariant KeepsWriteWhileAdvisorEngaged is violated by the initial state:\r\n      gap = 1\r\n        \\* The other half, which the sentence implies and which is the part that makes the policy useful:\r\n        \\* while the advisor IS engaged, the agent can still work.\r\n        KeepsWriteWhileAdvisorEngaged ==\r\n            (gap \u003C= 15 * Minute) =\u003E TradeAllowed(gap)\r\n\r\nThe policy does not mean what the property says it means. The state above is the\r\nrequest that breaks the claim, and the claim is quoted beneath it -- read the two\r\ntogether, because a violated invariant says which direction failed only when you can\r\nsee what it asserted.\r\n\r\nIn Dogwood\u0027s own terms:\r\n\r\n  KeepsWriteWhileAdvisorEngaged\r\n      TLC found      gap = 1\r\n      which is       @1 interact_advisor::response  @2 execute_trade::request\r\n      dogwood says   DENY at t=2  -- confirms the finding\r\n      so             with gap = 1, the Dogwood engine REFUSES this session at t=2, where \u0060KeepsWriteWhileAdvisorEngaged\u0060 says your policy must ALLOW it\r\n\r\n      @1 scope(principal: AgentCore::OAuthUser::\u0022agent\u0022, resource: AgentCore::Gateway::\u0022gw\u0022) AgentCore::Action::\u0022interact_advisor\u0022::response(input: { }, output: { }, callerPrincipal: AgentCore::OAuthUser::\u0022agent\u0022, callerResource: AgentCore::Gateway::\u0022gw\u0022, requestId: \u0022e1\u0022)\r\n      @2 scope(principal: AgentCore::OAuthUser::\u0022agent\u0022, resource: AgentCore::Gateway::\u0022gw\u0022) request_context(input: { }) AgentCore::Action::\u0022execute_trade\u0022::request(input: { }, callerPrincipal: AgentCore::OAuthUser::\u0022agent\u0022, callerResource: AgentCore::Gateway::\u0022gw\u0022, requestId: \u0022e2\u0022)\r\n\r\n      save that beside the policy and a generated Cedar schema and\r\n      the engine will answer you too:\r\n        dogwood replay --policy-schema generated.cedarschema --trace KeepsWriteWhileAdvisorEngaged.log 07-trust-decay.dw\r\n      (\u0060--keep DIR\u0060 writes all three, with a README)\r\n\r\n","exitCode":1,"propertyBroken":true,"inert":[],"unsettled":[]}
```

</details>

No, the policy `examples/aws1/07-trust-decay.dw` does not fully mean "

After 15 minutes without advisor interaction, the agent loses access to write operations," as the formal claim `KeepsWriteWhileAdvisorEngaged` is violated.

This means that the policy *denies* write operations even when the advisor *is* engaged (i.e., less than 15 minutes have passed since advisor interaction), which contradicts the expectation that operations should be allowed in this state.

Specifically, the claim `KeepsWriteWhileAdvisorEngaged` states that "whenever the `gap` (time without advisor interaction) is at most 15 minutes (900 seconds), then the policy GRANTS write operations (`TradeAllowed(gap)`)."

Here is a concrete situation where the policy does the wrong thing:

When the `gap` is 1 second (meaning advisor interaction just occurred), the policy `DENIES` the trade request. This contradicts the claim that the policy should `ALLOW` the trade request when the `gap` is less than or equal to 15 minutes.

The session that demonstrates this is:

*   **@1** An `interact_advisor::response` event occurs.
*   **@2** 1 second later, an `execute_trade::request` event occurs.

In this scenario, the Dogwood engine denies the `execute_trade::request` at time `t=2`, even though only 1 second has passed since the advisor interaction.

**Important Note on Reading:** The check was performed assuming an UNPINNED reading (global trace). Dogwood's own default pins `callerPrincipal` on every kind, meaning a deployed rule sees only its own principal's events. A rule reported live here may never fire under that default reading.

You can replay this specific situation yourself with the `dogwood replay` command using the following trace:

```
@1 scope(principal: AgentCore::OAuthUser::"agent", resource: AgentCore::Gateway::"gw") AgentCore::Action::"interact_advisor"::response(input: { }, output: { }, callerPrincipal: AgentCore::OAuthUser::"agent", callerResource: AgentCore::Gateway::"gw", requestId: "e1")
@2 scope(principal: AgentCore::OAuthUser::"agent", resource: AgentCore::Gateway::"gw") request_context(input: { }) AgentCore::Action::"execute_trade"::request(input: { }, callerPrincipal: AgentCore::OAuthUser::"agent", callerResource: AgentCore::Gateway::"gw", requestId: "e2")
```

## 3. Would a tighter rule hold too?

**Asked:**

> Suppose I wanted the agent to lose write access after ten minutes rather than fifteen. Does this policy already give me that, or would I have to change it?
> 
> The policy file is examples\aws1\07-trust-decay.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `DescribePolicyModule`

```json
{"policy": "examples\\aws1\\07-trust-decay.dw"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"module":{"source":"07-trust-decay.dw","reading":"no --event-schema given, so every answer below assumes the UNPINNED reading\n  (global trace). DOGWOOD\u0027S OWN DEFAULT IS THE OPPOSITE: it pins callerPrincipal\n  on every kind, so a deployed rule sees only its own principal\u0027s events and one\n  reported live here may never fire. Pass --pinned to check that reading, or\n  --event-schema for a real one.","module":"PolicyUnderTest","actions":["execute_trade","interact_advisor"],"kinds":["request","response"],"decisionKind":"request","inputFields":[],"outputFields":[],"pinKeys":[],"rules":[{"index":1,"effect":"permit","actions":["execute_trade"]}],"operators":{"Request(action, input)":"one request as the evaluator reads it, at time 1","Ev(action, kind, input, output, time)":"ONE EVENT AT A CHOSEN TIME AND KIND -- what a claim about a SESSION is built from. \u0060action\u0060 and \u0060kind\u0060 are PLAIN strings and \u0060time\u0060 a PLAIN integer -- Ev(\u0022trade\u0022, \u0022request\u0022, NoFields, NoFields, 900), never Str(\u0022trade\u0022) or Num(900). Tagging is for field VALUES inside the input/output records and nowhere else. \u0060time\u0060 is in SECONDS: a claim about a 15m window needs events 900 apart, not two","NoFields":"an empty input or output record","D!Decide(trace, Policies, i, AllValues)":"the verdict for event \u0060i\u0060 of a trace you built -- a sequence of Ev(...), in time order. This is how a TEMPORAL claim is stated; \u0060Grants\u0060 in the skeleton is the one-event shorthand","Policies":"the rule set, as the sequence Decide evaluates","AllValues":"every value any field may take -- Decide\u0027s last argument","InputDomain":"[field |-\u003E {values}] for the fields above","OutputDomain":"[field |-\u003E {values}] for the output fields","PinKeys":"the fields a universal pin partitions on; empty means global-trace"},"constructors":{"Str(x)":"a string","Num(x)":"an integer","Bool(x)":"TRUE or FALSE","Addr(a, b, c, d)":"an address, FOUR OCTETS -- TLC works in Java ints, so 208.4.4.0 as 3489924096 is not a value it can hold","Anon":"the anonymous principal/resource/session a per-request claim uses"},"rules_for_writing_one":["EXTENDS PolicyUnderTest, and instantiate DogwoodSemantics with Cases \u003C- \u003C\u003C \u003E\u003E.","Scalars are TAGGED. Write Num(22), never 22 -- TLC refuses a cross-kind comparison rather than quietly answering one.","There is no Inputs. State the requests your claim is about, including values this policy never mentions, or the claim may range over nothing and pass.","The .cfg must name SPECIFICATION Spec and every INVARIANT. A property nobody listed is a property nobody checked."],"skeleton":"---------------------------- MODULE P_07_trust_decay ----------------------------\n\\* What 07-trust-decay.dw is SUPPOSED to mean, stated by its author. The three built-in findings\n\\* (VACUOUS, REDUNDANT/DEAD, diff) are the claims statable WITHOUT knowing intent; this is the\n\\* other kind, and only the author can write it.\n\\*\n\\* SAVE THIS AS P_07_trust_decay.tla -- TLA\u002B requires the file name to match the module name, and a\n\\* module name may not contain \u0060-\u0060 or \u0060.\u0060 or begin with a digit, so it is not always the policy\u0027s\n\\* own name.\n\\*\n\\* Check it with:  python src/checker/properties.py 07-trust-decay.dw --property P_07_trust_decay.tla\nEXTENDS Integers, Sequences, FiniteSets, PolicyUnderTest\n\nD == INSTANCE DogwoodSemantics WITH Cases \u003C- \u003C\u003C \u003E\u003E\n\n\\* The verdict for one request. No session: \u0022what does this policy decide for this request\u0022 is\n\\* not a temporal question, so there is no state machine beyond holding one request still.\nGrants(input) == D!Decide(\u003C\u003CRequest(\u0022execute_trade\u0022, input)\u003E\u003E, Policies, 1, AllValues)\n\n(***************************************************************************)\n(* THE REQUESTS THIS CLAIM IS ABOUT.                                       *)\n(*                                                                         *)\n(* Written out rather than derived from InputDomain, and that is the       *)\n(* point. A space derived from the policy\u0027s own literals cannot test a     *)\n(* claim about a value the policy never mentions: delete the rule that     *)\n(* names a value and it vanishes from the vocabulary, so the claim ranges  *)\n(* over nothing and PASSES having looked at nothing.                       *)\n(*                                                                         *)\n(* Add the values your claim is about, including ones this policy never    *)\n(* mentions.                                                               *)\n(***************************************************************************)\n\\* This policy reads no input fields, so one request is the whole space.\nRequests == {[f \\in {} |-\u003E Str(\u0022\u0022)]}\n\n\\* One request, chosen nondeterministically and held, so a violation\u0027s counterexample NAMES the\n\\* request that breaks the claim rather than merely reporting that one exists.\nVARIABLE req\nInit == req \\in Requests\nNext == UNCHANGED req\nSpec == Init /\\ [][Next]_req\n\n(***************************************************************************)\n(* THE CLAIM.                                                              *)\n(***************************************************************************)\nEverythingIsGranted == Grants(req)\n\n=============================================================================\n","config":"SPECIFICATION Spec\n\n\\* Naming the claims is deliberate. A property nobody listed is a property\n\\* nobody checked.\nINVARIANT EverythingIsGranted\n"}}
```

</details>

**Tool call 2** — `ListKnowledge`

```json
{}
```

<details><summary>tool result (success)</summary>

```
[{"name":"event-schemas-and-pins","title":"Event schemas and pins","description":"Why passing a .dwschema changes what a policy MEANS, not merely what is checked.","uri":"anchor://knowledge/event-schemas-and-pins"},{"name":"reading-verdicts","title":"Reading a verdict","description":"What VACUOUS, REDUNDANT, DEAD, live and unknown mean, and what each one does not mean.","uri":"anchor://knowledge/reading-verdicts"},{"name":"smoke-vs-exhaustive","title":"Smoke versus exhaustive","description":"What a random walk can and cannot settle here \u2014 and why the polarity is backwards from every other smoke test.","uri":"anchor://knowledge/smoke-vs-exhaustive"},{"name":"the-modelled-subset","title":"The modelled subset, and why a refusal is not a failure","description":"What Anchor will and will not translate, and why it refuses rather than approximating.","uri":"anchor://knowledge/the-modelled-subset"},{"name":"what-anchor-does-not-check","title":"What Anchor does not check","description":"The limits to state alongside any verdict, so a bounded answer is not reported as a proof.","uri":"anchor://knowledge/what-anchor-does-not-check"},{"name":"writing-a-property-module","title":"Writing a property module","description":"How to state what a policy is SUPPOSED to mean, and the trap that makes such a claim pass having checked nothing.","uri":"anchor://knowledge/writing-a-property-module"}]
```

</details>

The `DescribePolicyModule` output for `examples\aws1\07-trust-decay.dw` indicates that the modeling environment, when interpreting temporal claims, defines a 15-minute window (900

seconds). Specifically, the description for the `Ev` operator states: "time is in SECONDS: a claim about a 15m window needs events 900 apart".

This implies that the policy, as currently modeled and checked, operates with a 15-minute decay period. The policy itself does not contain explicit input fields to configure this time duration within its Dogwood rules.

Therefore, to change the decay period from fifteen minutes to ten minutes, you would likely need to modify the underlying modeling of events or the way the policy is interpreted within the checking framework, rather than making a direct change to the `07-trust-decay.dw` policy file itself. The policy does not already provide for a 10-minute decay; a change would be required.

## 4. Do my two protections actually both apply?

**Asked:**

> This policy set is supposed to protect trades two ways: the profile being traded against must be one this session actually loaded, and the price must be less than 30 seconds old. I have written that out at `examples/aws1/TradeGate.tla`. Are both really required, or can a trade get through with only one of them satisfied?
> 
> The policy file is examples\aws1\agent-policy.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `ExplainPropertyModule`

```json
{"property": "examples/aws1/TradeGate.tla"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"explanation":{"module":"TradeGate.tla","states":["prereq = \u0022both\u0022","prereq = \u0022freshPriceOnly\u0022","prereq = \u0022neither\u0022","prereq = \u0022profileOnly\u0022","prereq = \u0022stalePriceOnly\u0022"],"scope":"read from Init","claims":[{"name":"FreshPriceAloneIsNotEnough","defined":true,"says":"whenever prereq is \u0022freshPriceOnly\u0022, then the policy REFUSES it (Allowed(prereq))","forbids":"prereq is \u0022freshPriceOnly\u0022, and yet the policy GRANTS it (Allowed(prereq))","condition":"prereq = \u0022freshPriceOnly\u0022","appliesTo":["prereq = \u0022freshPriceOnly\u0022"],"states":5,"unknownIn":0,"settledWithoutThePolicy":4,"falseWithoutThePolicy":[],"vacuous":false,"notes":[]}],"definedButNotChecked":["BothIsAllowed","NothingAllowsNoTrade","ProfileAloneIsNotEnough","RequiresBothChecks"],"vacuous":[]}}
```

</details>

It looks like your property module `TradeGate.tla` defines a claim `FreshPriceAloneIsNotEnough`, which states that if a trade only satisfies the fresh price condition (`prereq = "fresh

PriceOnly"`), then the policy should refuse it. The claim forbids the scenario where the fresh price condition is met, but the policy *grants* the trade.

However, I noticed that another related claim, `ProfileAloneIsNotEnough`, is defined in your module but is currently *not checked*. This means the current configuration would not tell us whether a trade can get through with only the profile loaded.

To fully answer your question about whether both are *really* required or if a trade can get through with *only one* satisfied, we would need to ensure `ProfileAloneIsNotEnough` is also checked.

For now, I will proceed with checking the `FreshPriceAloneIsNotEnough` claim against your policy `examples/aws1/agent-policy.dw`.

**Tool call 2** — `CheckPolicy`

```json
{"policy": "examples/aws1/agent-policy.dw", "property": "examples/aws1/TradeGate.tla"}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"no --event-schema given, so every answer below assumes the UNPINNED reading\r\n  (global trace). DOGWOOD\u0027S OWN DEFAULT IS THE OPPOSITE: it pins callerPrincipal\r\n  on every kind, so a deployed rule sees only its own principal\u0027s events and one\r\n  reported live here may never fire. Pass --pinned to check that reading, or\r\n  --event-schema for a real one.\r\n\r\nagent-policy.dw against TradeGate.tla: 7 rule(s)\r\n\r\n  BROKEN  Invariant FreshPriceAloneIsNotEnough is violated by the initial state:\r\n      prereq = \u0022freshPriceOnly\u0022\r\n        FreshPriceAloneIsNotEnough ==\r\n            (prereq = \u0022freshPriceOnly\u0022) =\u003E ~Allowed(prereq)\r\n\r\nThe policy does not mean what the property says it means. The state above is the\r\nrequest that breaks the claim, and the claim is quoted beneath it -- read the two\r\ntogether, because a violated invariant says which direction failed only when you can\r\nsee what it asserted.\r\n","exitCode":1,"propertyBroken":true,"inert":[],"unsettled":[]}
```

</details>

**Tool call 3** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

The model checking results for `examples/aws1/agent-policy.dw` against your

property module `examples/aws1/TradeGate.tla` indicate that **the policy allows a trade to go through even when only the price is fresh, and the profile has not necessarily been loaded.**

Specifically, the claim `FreshPriceAloneIsNotEnough` in your property module was found to be **BROKEN**. This claim asserted that if `prereq` is `"freshPriceOnly"` (meaning only the fresh price condition is met), then the policy should *refuse* the trade. The fact that it is broken means the policy *grants* the trade in such a scenario.

This means that, contrary to the intention expressed in the `FreshPriceAloneIsNotEnough` claim, **both conditions are NOT strictly required; a trade can get through with only the fresh price condition satisfied.**

It is important to note that your property module also defines a claim `ProfileAloneIsNotEnough`, which would address the other scenario (only the profile is loaded). However, this claim was listed as `definedButNotChecked`, so the current analysis does not provide a verdict on that specific condition. If you wish to check that scenario as well, you would need to ensure `ProfileAloneIsNotEnough` is included in the checks.

## 5. What did my edit change?

**Asked:**

> I have two versions of this policy. Tell me whether the first one allows anything the second one does not, and show me a concrete example of it.
> 
> The policy file is examples\aws1\agent-policy.dw.
> 
> The second policy file, to compare against, is examples\aws1\03-data-freshness.dw.

| | |
|---|---|
| provider | auto |
| model | (provider default) |

**Tool call 1** — `CheckPolicy`

```json
{
  "against": "examples\u0007ws1\u0003-data-freshness.dw",
  "policy": "examples\u0007ws1\u0007gent-policy.dw",
  "trace": true
}
```

<details><summary>tool result (success)</summary>

```
{"answered":false,"findings":[],"output":"","error":"no such policy file: C:\\Projects\\Anchor\\examples\u0007ws1\u0007gent-policy.dw","exitCode":2,"propertyBroken":false,"inert":[],"unsettled":[]}
```

</details>

**Tool call 2** — `CheckPolicy`

```json
{
  "against": "examples\\aws1\\03-data-freshness.dw",
  "policy": "examples\\aws1\\agent-policy.dw",
  "trace": true
}
```

<details><summary>tool result (success)</summary>

```
{"answered":true,"reading":"no event schema given, so every answer assumes the UNPINNED reading (global trace); the shipped default partitions by principal, under which a rule reported live here may never fire","findings":[],"output":"{\r\n  \u0022policy\u0022: \u0022agent-policy.dw\u0022,\r\n  \u0022against\u0022: \u002203-data-freshness.dw\u0022,\r\n  \u0022reading\u0022: \u0022no --event-schema given, so every answer below assumes the UNPINNED reading (global trace). DOGWOOD\u0027S OWN DEFAULT IS THE OPPOSITE: it pins callerPrincipal on every kind, so a deployed rule sees only its own principal\u0027s events and one reported live here may never fire. Pass --pinned to check that reading, or --event-schema for a real one.\u0022,\r\n  \u0022bound\u0022: {\r\n    \u0022attempts\u0022: 3,\r\n    \u0022amount\u0022: 2,\r\n    \u0022exhaustive\u0022: true,\r\n    \u0022randomSessions\u0022: null\r\n  },\r\n  \u0022verdict\u0022: \u0022MORE PERMISSIVE\u0022,\r\n  \u0022added\u0022: {\r\n    \u0022witness\u0022: \u0022get_client_profile\u0022,\r\n    \u0022session\u0022: [\r\n      {\r\n        \u0022action\u0022: \u0022get_client_profile\u0022,\r\n        \u0022kind\u0022: \u0022request\u0022,\r\n        \u0022input\u0022: {\r\n          \u0022profile_id\u0022: 1\r\n        },\r\n        \u0022output\u0022: {},\r\n        \u0022time\u0022: 1,\r\n        \u0022principal\u0022: \u0022caller\u0022,\r\n        \u0022resource\u0022: \u0022caller\u0022,\r\n        \u0022session\u0022: \u0022caller\u0022,\r\n        \u0022pins\u0022: {}\r\n      },\r\n      {\r\n        \u0022action\u0022: \u0022get_client_profile\u0022,\r\n        \u0022kind\u0022: \u0022response\u0022,\r\n        \u0022input\u0022: {\r\n          \u0022profile_id\u0022: 1\r\n        },\r\n        \u0022output\u0022: {},\r\n        \u0022time\u0022: 2,\r\n        \u0022principal\u0022: \u0022caller\u0022,\r\n        \u0022resource\u0022: \u0022caller\u0022,\r\n        \u0022session\u0022: \u0022caller\u0022,\r\n        \u0022pins\u0022: {}\r\n      }\r\n    ],\r\n    \u0022narrative\u0022: [\r\n      \u00221. get_client_profile(profile_id = 1)  allowed\u0022\r\n    ]\r\n  },\r\n  \u0022removed\u0022: null,\r\n  \u0022artifacts\u0022: null\r\n}\r\n","exitCode":0,"propertyBroken":false,"inert":[],"unsettled":[]}
```

</details>

**Tool call 3** — `ReadKnowledge`

```json
{"names": ["reading-verdicts"]}
```

<details><summary>tool result (success) — clipped</summary>

```
[{"name":"reading-verdicts","title":"Reading a verdict","uri":"anchor://knowledge/reading-verdicts","content":"# Reading a verdict\n\n\u0060CheckPolicy\u0060 reports one verdict per rule. They are not style notes. Each answers the same\nunderlying question \u2014 *does deleting or changing this rule change what the policy decides?* \u2014 and\nevery answer is either **a witness session** or **a bounded no**.\n\n| verdict | means | what to do |\n|---|---|---|\n| \u0060live\u0060 | the rule changes some verdict; the witness names the session that proves it | nothing. It is load-bearing |\n| \u0060VACUOUS\u0060 | a permit that never grants anything in any session searched | treat as a **bug**. Whatever it was meant to allow is unreachable |\n| \u0060REDUNDANT\u0060 | a permit that fires, but another permit always would too | it can be deleted without changing behaviour |\n| \u0060DEAD\u0060 | a forbid that never denies anything the rest of the set would have allowed | it can be deleted without changing behaviour |\n| \u0060unknown\u0060 | only from a smoke run: no witness found by a random walk | **not a verdict**. See \u0060smoke-vs-exhaustive\u0060 |\n\n## VACUOUS is the serious one\n\nA vacuous permit is not untidiness. It is a control that authorizes nothing while reading as though\nit authorizes something \u2014 it parses, it validates, and \u0060dogwood validate\u0060 accepts it. Nothing in the\npolicy text says so. If you report one, say plainly that the rule grants nothing, not that it is\n\u0022possibly redundant\u0022.\n\n## Every negative answer is bounded, and the bound is printed\n\n\u0060VACUOUS\u0060 means *no session of up to \u0060attempts\u0060 attempts makes it grant*. It does not mean \u0022never\u0022.\nThe same applies to \u0060REDUNDANT\u0060, \u0060DEAD\u0060, and to \u0060EQUIVALENT\u0060 from an \u0060against\u0060 comparison.\n\nSo when you report one of these, report the bound with it. \u0022Vacuous within 3 attempts\u0022 is true;\n\u0022vacuous\u0022 alone overstates what was checked. Raising \u0060attempts\u0060 trades runtime for confidence.\n\nA \u0060live\u0060 verdict has no such caveat: a witness exists, and it was exhibited.\n\n## The witness, and the session under it\n\nFor a \u0060live\u0060 rule the note carries the session that proves it, as the actions attempted in order \u2014\n\u0060Approve -\u003E Trade\u0060. That is the shortest thing to quote when explaining why a rule matters.\n\n**Quote the session, not just the action names, whenever the checker prints one.** Under the\nsummary line the output tells the same session as numbered attempts with the values passed and\nwhat each one got:\n\n\u0060\u0060\u0060\n1. Connect(src = 10.0.0.0)  denied\n2. Connect(src = 11.0.0.0)  allowed\n\u0060\u0060\u0060\n\n\u0060Connect\u0060 is true and nearly useless \u2014 it cannot say whether the connection that got through came\nfrom inside the network or outside it, and that distinction is the whole content of a firewall\npolicy. The session can. When you explain a verdict to someone, this is the part that makes it\nconcrete, and it needs no knowledge of TLA\u002B to read.\n\nFor an edit comparison the last attempt is marked with what the *other* policy would have done at\nthat point. That line is the finding; everything above it is the setup that made it reachable.\n\n## Comparing an edit: report the DIRECTION, never just \u0022they differ\u0022\n\nGiven \u0060against\u0060, the checker answers a different question \u2014 not \u0022is each rule doing something\u0022 but\n**what did this edit change**. Four verdicts:\n\n| | |\n|---|---|\n| \u0060MORE PERMISSIVE\u0060 | the new set allows sessions the old one denied \u2014 **it added permissions** |\n| \u0060LESS PERMISSIVE\u0060 | the new set denies sessions the old one allowed |\n| \u0060EQUIVALENT\u0060 | no session within the bound tells them apart |\n| \u0060INCOMPARABLE\u0060 | both at once, which is usually a mistake rather than an intention |\n\n**\u0060MORE PERMISSIVE\u0060 is the one to lead with, even when the person asked about the other\ndirection.** Someone editing a policy usually wants to know what they took away, because that is\nwhat generates complaints. What they need to know is what they added: a permission removed is a\nsupport ticket, a permission silently added is an incident. Quote the \u0060ADDED\u0060 witness session.\n\nDo not soften \u0060INCOMPARABLE\u0060 into \u0022some changes\u0022. It means the edit moved in both directions at\nonce \u2014 almost always a condition that was rewritten rather than extended, and worth asking about.\n\n\u0060EQUIVALENT\u0060 is a claim of absence, so it carries the bound like every other one. It licenses \u0022no\nsession of up to N attempts tells them apart\u0022, not \u0022the edit is safe\u0022.\n\n## Why it is inert, not just that it is\n\nUnder an inert rule the checker says which part of it is responsible. Two shapes, and they call\nfor different advice:\n\n| | |\n|---|---|\n| \u0060because: \u003Cterms\u003E\u0060 | **these terms** are the reason. Removing any one of them revives the rule |\n| \u0060the condition is not why\u0060 | it is inert **even with no condition at all** \u2014 the reason is structural |\n\n**Quote the terms.** \u0022This forbid never denies anything\u0022 sends someone back to re-read their own\ncondition; \u0022it cannot fire because \u0060input.origin == nowhere \u0026\u0026 input.origin == local\u0060\u0022 tells them\nwhat to change. The terms are read from the *parsed* form, so if one looks unlike what they wrote,\nthat disagreement is itself worth raising.\n\n**A structural answer means do not touch the condition.** The usual cause is that nothing the rule\nguards was ever permitted \u2014 a forbid over an action with no permit, or one whose only permit is\nitself VACUOUS. Editing the condition there changes nothing, and suggesting it wastes the reader\u0027s\ntime on the wrong file.\n\nThe set is **minimal, 
…
```

</details>

The first policy (`examples\aws1\agent-policy.

dw`) is **MORE PERMISSIVE** than the second policy (`examples\aws1\03-data-freshness.dw`). This means that `agent-policy.dw` allows sessions that `03-data-freshness.dw` would have denied.

Here is a concrete example of a session that the first policy allows but the second policy does not, based on a bound of 3 attempts and an amount of 2:

**Witness Session:**
1.  **Action:** `get_client_profile`
    *   **Kind:** `request`
    *   **Input:** `profile_id: 1`
    *   **Time:** 1
    *   **Principal:** `caller`
    *   **Resource:** `caller`
    *   **Session:** `caller`
2.  **Action:** `get_client_profile`
    *   **Kind:** `response`
    *   **Input:** `profile_id: 1`
    *   **Time:** 2
    *   **Principal:** `caller`
    *   **Resource:** `caller`
    *   **Session:** `caller`

**Narrative:** `get_client_profile(profile_id = 1)` is allowed by the first policy.

**Note:** This analysis was performed assuming an **UNPINNED reading** (a global trace) because no event schema was provided. Dogwood's own default partitions by principal, so a rule reported live here may never fire in a deployed scenario using that default.
