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
