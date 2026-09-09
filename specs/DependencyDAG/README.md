# DependencyDAG

A model of a **multi-agent workflow graph**: several tasks, each waiting on others, run by an
orchestrator. It answers two questions about any such graph — *does a task ever start before its
dependencies are done?* and *does the whole graph always finish?* — and it answers them for a graph
**translated automatically from a live Amazon Strands `Graph` object**, not from one written by
hand.

| file | what it is |
|---|---|
| `DependencyDAG.tla` | the model: states, transitions, and the properties. Verifies. |
| `DependencyDAG.cfg` | tells the checker which properties to check. |
| `Bug5_NoFailurePropagation.tla` | the same model with one deliberate mistake. **Expected to fail.** |
| `Bug5_NoFailurePropagation.cfg` | |
| `Workflow.tla` | the *graph* — separated out so it can be swapped. Hand-written here. |
| `anchor_conditions.py` | Strands edge conditions that carry their own TLA+ meaning. |

The generator that emits `Workflow.tla` from a real Strands graph lives in
[`tests/strands/graph_to_tla.py`](../../tests/strands/graph_to_tla.py), and the test that checks
those conditions mean what they say is
[`tests/strands/condition_differential.py`](../../tests/strands/condition_differential.py).

```bash
python tests/strands/graph_to_tla.py
```

---

# Part 1 — TLA+ for someone who has never seen it

Skip to [Part 3](#part-3--translating-a-strands-graph-into-this-model) if you already read TLA+.

## What TLA+ is, and what the checker does

TLA+ is a language for describing a **state machine**: what the state is, what it starts as, and
what steps are allowed. You do not write a program. You write down the set of all possible
behaviours, and then state properties that must be true of every one of them.

TLC — the checker — takes that description and **explores every reachable state**, exhaustively. Not
samples, not tests: every state the machine can get into, and every order the steps can happen in.
If a property can be broken, TLC finds the shortest sequence of steps that breaks it and prints it
as a **counterexample trace**.

That exhaustiveness is the point. The bug this directory exists to document — a task starting before
its dependency finished — only shows up in *some* interleavings. A test would have to be lucky. TLC
is not lucky; it is complete.

## The notation, symbol by symbol

Everything used in these files, in the order you will meet it.

### Structure

```tla
---------------------------- MODULE DependencyDAG ----------------------------
EXTENDS Naturals, FiniteSets, Workflow
...
=============================================================================
```

A file is one **module**, whose name must match the filename. `EXTENDS` pulls in other modules —
`Naturals` for arithmetic, and `Workflow` for the graph. That last one is how a generated graph gets
plugged into a hand-written model: `DependencyDAG` extends `Workflow`, so replacing `Workflow.tla`
replaces the workflow without touching the properties.

```tla
\* a one-line comment

(***************************************************************************)
(* a block comment                                                         *)
(***************************************************************************)
```

### Definitions

`==` means *is defined as*. It is not assignment; nothing is ever assigned in TLA+.

```tla
Terminal == {"COMPLETED", "FAILED", "CANCELED"}     \* a set of three strings
Done(t)  == state[t] = "COMPLETED"                  \* a definition taking a parameter
```

A single `=` is **comparison**, as in ordinary mathematics. `#` is "not equal".

### Sets and tuples

| | |
|---|---|
| `{"a", "b"}` | a set. Unordered, no duplicates. |
| `{}` | the empty set. |
| `<<"a", "b">>` | a *tuple* — ordered, fixed length. Used here for an edge: `<<from, to>>`. |
| `x \in S` | `x` is a member of `S`. |
| `x \notin S` | it is not. |
| `{p \in Tasks : <<p, t>> \in Edges}` | **set comprehension** — every `p` in `Tasks` for which the condition holds. Read the `:` as "such that". |

### Logic

| | |
|---|---|
| `/\` | AND |
| `\/` | OR |
| `~` | NOT |
| `=>` | implies. `A => B` is false only when `A` is true and `B` is false. |
| `\A x \in S : P` | **for all** `x` in `S`, `P` holds. |
| `\E x \in S : P` | **there exists** an `x` in `S` for which `P` holds. |

`/\` and `\/` are usually written as an indented list, which is just a readable way to write a long
conjunction. These two are identical:

```tla
Start(t) == /\ state[t] = "READY"
            /\ state' = [state EXCEPT ![t] = "IN_PROGRESS"]

Start(t) == (state[t] = "READY") /\ (state' = [state EXCEPT ![t] = "IN_PROGRESS"])
```

The indentation is significant — items must line up under each other.

Two gotchas worth knowing early:

- **`\A` over an empty set is TRUE.** `\A p \in {} : anything` holds vacuously. That is why a task
  with no dependencies is automatically allowed to start.
- **`\E` over an empty set is FALSE.** Which is why the model has to special-case entry points.

### Functions

A TLA+ *function* is closer to a lookup table than to a subroutine.

| | |
|---|---|
| `[Tasks -> States]` | the **set of all functions** from `Tasks` to `States`. |
| `[t \in Tasks \|-> "BLOCKED"]` | one such function: every task maps to `"BLOCKED"`. |
| `state[t]` | apply the function — the state of task `t`. |
| `DOMAIN f` | the set of inputs `f` is defined on. |

Applying a function outside its domain is an **error**, not a default value. That is load-bearing
here: it is how a mis-declared condition gets caught (see Part 3).

`EXCEPT` builds a new function that differs at one point:

```tla
[state EXCEPT ![t] = "READY"]
```

means *the same function as `state`, except that `t` now maps to `"READY"`*. Nothing is mutated — it
is a new value.

### CASE

```tla
EdgeCond(from, to, st) ==
    CASE <<from, to>> = <<"t1", "t3">> -> AllComplete({"t1", "t2"}, st)
      [] <<from, to>> = <<"t2", "t3">> -> AllComplete({"t1", "t2"}, st)
      [] OTHER                         -> TRUE
```

A multi-way choice. The first arm gets `CASE`, the rest get `[]`, and `OTHER` is the fallback. This
particular shape is what the generator emits, one arm per conditional edge.

### Primes, and what a "step" is

This is the one genuinely unfamiliar idea.

An **unprimed** variable is its value *before* a step. A **primed** variable is its value *after*.
So an action is a relation between two consecutive states:

```tla
Succeed(t) ==
    /\ state[t] = "IN_PROGRESS"                        \* precondition, on the OLD state
    /\ state' = [state EXCEPT ![t] = "COMPLETED"]      \* what the NEW state must be
    /\ UNCHANGED oracle                                \* everything else stays put
```

Read it as: *this step is possible when `t` is in progress, and taking it produces a state in which
`t` is completed and `oracle` is unchanged.* An action is not a command — it is a description of
which state pairs count as a legal step.

`UNCHANGED x` is shorthand for `x' = x`. **Every variable must be constrained in every action**, or
the model would allow it to change arbitrarily.

### Putting a machine together

```tla
Init == /\ state = [t \in Tasks |-> "BLOCKED"]
        /\ oracle \in [NondetEdges -> BOOLEAN]

Next == \E t \in Tasks : Unblock(t) \/ Start(t) \/ Succeed(t) \/ Fail(t) \/ CancelOrphan(t)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
```

- `Init` says which states may be *initial*. Note `oracle \in [...]` rather than `oracle = ...`:
  that is a **nondeterministic choice**, so TLC explores one behaviour per possible value.
- `Next` says which steps are allowed: *there exists some task `t` such that one of these actions
  happens to it*. This is where concurrency comes from — TLC tries every task, in every order.
- `Spec` is the whole machine. `[][Next]_vars` means "every step is a `Next` step, or changes
  nothing". `WF_vars(Next)` is **weak fairness**: if a step stays possible forever, it eventually
  happens. Without it, a machine that simply stops doing anything would satisfy every liveness
  property vacuously.

### Properties

**Invariants** are checked in every reachable state:

```tla
HP10 ==
    \A t \in Tasks :
        state[t] \in {"IN_PROGRESS", "COMPLETED"} => \A p \in Deps[t] : state[p] = "COMPLETED"
```

**Temporal properties** are about whole behaviours:

| | |
|---|---|
| `<>P` | *eventually* `P` — at some point, in every behaviour. |
| `[]P` | *always* `P`. |
| `[][A]_vars` | every step satisfies `A` (or changes nothing). |

```tla
AllTerminate == <>(\A t \in Tasks : state[t] \in Terminal)      \* the graph always finishes
```

### The `.cfg` file

TLC needs to be told what to run:

```
SPECIFICATION Spec
CHECK_DEADLOCK FALSE
INVARIANT TypeOK
INVARIANT HP10
INVARIANT NoOrphanRuns
PROPERTY AllTerminate
PROPERTY TerminalIsFinal
```

`CHECK_DEADLOCK FALSE` matters. TLC normally reports "no step is possible" as a bug. Here it is what
*success* looks like — every task has finished and nothing more should happen — so the check is
turned off.

---

# Part 2 — the model

## The state

One variable holds the whole workflow: a function from task name to state.

```
BLOCKED ──> READY ──> IN_PROGRESS ──┬──> COMPLETED
    │                               └──> FAILED
    └──> CANCELED
```

Six states, three of them terminal. A second variable, `oracle`, is explained in Part 3 — it stands
in for conditions whose meaning was never declared.

## The transitions

| action | when | effect |
|---|---|---|
| `Unblock(t)` | `t` has no incoming edges, **or** one incoming edge fires | `BLOCKED → READY` |
| `Start(t)` | `t` is `READY` | `READY → IN_PROGRESS` |
| `Succeed(t)` | `t` is running | `IN_PROGRESS → COMPLETED` |
| `Fail(t)` | `t` is running | `IN_PROGRESS → FAILED` |
| `CancelOrphan(t)` | no incoming edge can ever fire | `BLOCKED → CANCELED` |

`Succeed` and `Fail` are both always available to a running task. Nothing decides which — TLC
explores both, so every property must hold whatever the agents do. That is deliberate: you cannot
verify a language model, so you verify the orchestration under a model permitted to behave as badly
as it likes.

**`Unblock` is where the interesting decision lives**, and it uses **OR**, not AND:

```tla
Unblock(t) ==
    /\ state[t] = "BLOCKED"
    /\ \/ Entry(t)                                  \* no parents: start immediately
       \/ \E p \in Deps[t] : CanFire(p, t)          \* or ONE parent admits it
    /\ state' = [state EXCEPT ![t] = "READY"]
    /\ UNCHANGED oracle
```

This is not a modelling preference. It is what Strands does, and getting it wrong was a real bug in
an earlier version of this model — see Part 3.

## The properties

| property | in English |
|---|---|
| `TypeOK` | every variable holds a value of the right shape. A sanity check that catches modelling slips. |
| `HP10` | no task is running or finished unless **all** its parents completed. |
| `NoOrphanRuns` | a task that can never be admitted is cancelled, never run. |
| `AllTerminate` | every task eventually reaches a terminal state. The graph finishes. |
| `TerminalIsFinal` | nothing that finished ever moves again. |

`HP10` is from Table 1 of Allegrini, Shreekumar & Celik, *Formalizing the Safety, Security, and
Functional Properties of Agentic AI Systems* (arXiv:2510.14133v2). The paper states it in CTL:

> `AG(∀i ∈ D : CL.invoke(EE, prot, sub_task_i) → ∀p ∈ parents(sub_task_i) : Completed(p))`

`AG` becomes `[]`, and since `COMPLETED` is only reachable through `IN_PROGRESS`, the invocation is
captured by checking the states an invocation leads to. The paper's `AF` maps to `<>`; its `EF` has
**no TLA+ form at all**, because TLA+ is linear-time and has no existential path quantifier.

## The bug variant

`Bug5_NoFailurePropagation.tla` is a byte-for-byte copy with **one** change: `CancelOrphan` is
removed from `Next`. It is defined, but never reachable.

TLC then finds: one task fails, everything downstream stays `BLOCKED`, and the graph never finishes.
And crucially — **no invariant is violated.** `HP10` holds throughout. `NoOrphanRuns` holds. Only
liveness fails.

An orchestrator audited against HP10 alone would pass this and then hang in production on the first
failed sub-task. So HP10 and the paper's TL1 (everything terminates) are *not independent*:
satisfying HP10 creates an obligation to cancel the orphaned subgraph, and Table 1 never states it.

The variant is the load-bearing half of this directory. A checker that only ever reports success
proves nothing; this pins down that a specific mistake is caught, and which property catches it.

---

# Part 3 — translating a Strands graph into this model

## Why translate rather than write the model by hand

A model written by reading code is a **paraphrase**, and nothing checks a paraphrase. Worse, a wrong
model does not fail — it verifies, and reports success about a workflow nobody is running.

A Strands `Graph` avoids this, because it is not a *description* of a workflow. `GraphBuilder` is the
construction API, so the object **is** the workflow and the runtime executes that same object.
Walking it is translation, not inference:

```
GraphBuilder ──> Graph ──> Workflow.tla ──┐
                                          ├──> TLC checks HP10 + termination
                   DependencyDAG.tla ─────┘
```

Only the graph is generated. The properties and the transitions live once, reviewed, in
`DependencyDAG.tla` — so a new workflow is checked against the same properties without anyone
rewriting them.

There is no DOT or mermaid export in the SDK to translate instead; the mermaid blocks in the Strands
docs are hand-drawn illustrations. The object graph is the better artifact anyway: no serialisation
format to drift, no parser to get wrong, and it is the same structure the runtime executes.

## What the generator reads

From the built `Graph` object, four things:

| Python | meaning |
|---|---|
| `graph.nodes` | dict of node id → `GraphNode`. |
| `graph.edges` | list of `GraphEdge`, each with `.from_node`, `.to_node`, `.condition`. |
| `edge.condition` | an optional callable deciding traversal at runtime, or `None`. |
| `condition.__anchor__` | the declared TLA+ meaning, if the condition carries one. |

And it emits **five** definitions into `Workflow.tla`.

## The five definitions, and where each comes from

### 1. `Tasks` — the nodes

```python
nodes = sorted(graph.nodes)
```
```tla
Tasks == {"analysis", "factcheck", "report", "research"}
```

Sorted so that regenerating an unchanged graph produces an identical file.

### 2. `Edges` — the graph, as pairs

```python
edges = sorted(graph.edges, key=lambda e: (e.from_node.node_id, e.to_node.node_id))
```
```tla
Edges == {<<"analysis", "report">>, <<"factcheck", "report">>,
          <<"research", "analysis">>, <<"research", "factcheck">>}
```

**Note what is *not* emitted.** An earlier version emitted `GraphNode.dependencies` as a per-node
`Deps` set. That was wrong, and the fix is the single most important thing in this directory — see
[the OR rule](#the-or-rule-and-why-the-first-model-was-wrong) below. `DependencyDAG.tla` now derives
the parent set itself:

```tla
Deps == [t \in Tasks |-> {p \in Tasks : <<p, t>> \in Edges}]
```

Deriving it means the graph and the thing `HP10` quantifies over cannot disagree.

### 3. `EdgeCond` — what each condition means

A Strands edge may carry a condition — an arbitrary Python callable run at traversal time:

```python
builder.add_edge("analysis", "report", condition=all_complete("analysis", "factcheck"))
```

`all_complete` comes from [`anchor_conditions.py`](anchor_conditions.py) and is **simultaneously a
real Strands condition and its own TLA+ predicate**. The generator reads the predicate off the
object and emits:

```tla
EdgeCond(from, to, st) ==
    CASE <<from, to>> = <<"analysis", "report">>  -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] <<from, to>> = <<"factcheck", "report">> -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] OTHER                                    -> TRUE
```

`OTHER -> TRUE` means an edge with no condition always traverses, which is Strands' default.

**Why `st` is a parameter and not a variable.** `Workflow` is *extended by* `DependencyDAG`, so it is
the lower module and cannot see the `VARIABLE state` declared above it. The state has to be passed
in. This also forces the predicate's vocabulary to stay closed: the only names it may use are its own
parameters, which is exactly why a condition reading an agent's output text cannot be expressed here
at all.

### 4. `EdgeSupport` — which tasks a condition reads

```tla
EdgeSupport(from, to) ==
    CASE <<from, to>> = <<"analysis", "report">>  -> {"analysis", "factcheck"}
      [] OTHER                                    -> {}
```

This exists for one job: telling a condition that is *false but might yet become true* from one that
**can never become true**.

```tla
EdgeDead(p, t) ==
    \/ state[p] \in {"FAILED", "CANCELED"}
    \/ /\ Done(p)
       /\ ~Traversable(p, t)
       /\ \A n \in EdgeSupport(p, t) : state[n] \in Terminal
```

Without it the model must guess, and both guesses are wrong: assume a false condition can always
flip and a guarded join can never be cancelled, so the graph never finishes; assume it cannot and a
live task gets cancelled while one of its dependencies is still running.

An **understated** support set is a real hazard, and it is caught rather than trusted — see
[checking the annotation](#checking-the-annotation-rather-than-trusting-it).

### 5. `NondetEdges` — conditions with no declared meaning

Some conditions genuinely cannot be given a predicate, because they read things the model does not
hold:

```python
def approved(state) -> bool:
    return "approve" in str(state.results["plan"].result).lower()
```

The agent's output text is not in the vocabulary. So nothing is claimed about it:

```tla
NondetEdges == {<<"plan", "approve">>, <<"plan", "reject">>}
```

and `DependencyDAG.tla` introduces a free choice standing in for whatever they decide:

```tla
VARIABLES state, oracle

Init == /\ state = [t \in Tasks |-> "BLOCKED"]
        /\ oracle \in [NondetEdges -> BOOLEAN]        \* one behaviour per combination

Traversable(p, t) ==
    IF <<p, t>> \in NondetEdges THEN oracle[<<p, t>>] ELSE EdgeCond(p, t, state)
```

Anything that verifies then holds **whatever those conditions decide** — nothing about them was
translated, so there is nothing to mistranslate.

When `NondetEdges` is empty, `[{} -> BOOLEAN]` contains exactly one function, so this costs nothing:
the checked-in specs generate the same 40 and 33 distinct states they did before `oracle` existed.

## The OR rule, and why the first model was wrong

This is the finding that reshaped the whole directory, and it is worth understanding in full.

`GraphNode.dependencies` looks like the parent set you should wait for. It is not. In
`Graph._is_node_ready_with_conditions`:

```python
for edge in incoming_edges:
    if edge.from_node in completed_batch:
        if edge.should_traverse(...):
            return True
return False
```

A node is ready as soon as the **first** incoming edge whose source completed passes its condition.
`dependencies` is used only to find entry points and to gather node inputs; **it never gates
execution.** The Strands documentation says so outright:

> In Python, the default behavior is OR semantics — a target node fires when **any** incoming edge's
> source completes. Use conditional edges to explicitly wait for all dependencies.

Modelling that as AND described a *stricter* orchestrator than the one that runs, which is the
unsound direction: HP10 verified against a discipline nothing enforces.

The four-node diamond hides it, because `analysis` and `factcheck` execute in one batch and `report`
sees both complete. A shape whose parents cannot share a batch does not hide it:

```
A ──> B ──> C
└───────────^
```

Against the real SDK, `execution_order` contains **C twice** — admitted once on the `A` edge while
`B` is still running, and again when `B` completes. And TLC finds the matching counterexample:

```
state = [A |-> "COMPLETED", B |-> "BLOCKED", C |-> "IN_PROGRESS"]
```

The remedy is a condition on the join, which is exactly what `all_complete` is for. Guarded, the
real SDK admits C once and TLC verifies HP10.

## The three tiers of condition

| tier | what it is | what is trusted |
|---|---|---|
| **0** | a combinator from `anchor_conditions.py` — `all_complete`, `any_complete`, `none_failed` | nothing per-workflow. Meaning is construction; reviewed and tested once. |
| **1** | `@condition_schema` on a user's own factory | the user's assertion about their own Python. Emitted as an `ASSUMED` block and counted. |
| **2** | no declaration at all | nothing — the condition is modelled as an unknown choice. |

The generator reports the tally, so holes cannot accumulate silently:

```
  assumed predicates: 0    not modelled: 2
```

### Why the annotation rides on the object rather than a source comment

A comment above `add_edge(...)` binds by **line adjacency**. It is invisible to the runtime, it
detaches silently when the call moves into a loop or a helper, and reading it at all requires parsing
the source — which is the thing this design exists to avoid. `edge.condition` is the same object
reference the scheduler calls, so annotating *it* binds by identity and survives refactoring.

`@condition_schema` wraps a **factory**, not a function, because in the pattern the Strands docs use
the arguments are what differ per edge:

```python
@condition_schema("AllComplete",
                  tla='\\A n \\in {required_nodes} : st[n] = "COMPLETED"',
                  support=("required_nodes",))
def all_dependencies_complete(required_nodes): ...
```

The wrapper stamps each closure the factory returns with the substituted predicate and the arguments
it was built from. Placeholders and support names are checked against the factory's real signature at
decoration time, so a typo fails at import rather than becoming literal text in a generated module.

## Checking the annotation rather than trusting it

An annotation is only better than a hand-written translator if its claim is actually checked —
otherwise it is the same silent-disagreement trap with nicer syntax.
[`condition_differential.py`](../../tests/strands/condition_differential.py) enumerates every
assignment of task states over a condition's declared support, asks the **real callable** for a
verdict on each, and has TLC compare that table against the predicate:

```
  all_complete("a", "b")                       36 states  combinator AGREE
  all_complete("a", "b", "c")                 216 states  combinator AGREE
  all_dependencies_complete(["a", "b"])        36 states  assumed    AGREE
  mistranslated(["a", "b"])                    36 states  assumed    DISAGREE
```

The last line is a deliberate mutation — `\E` where the callable means `\A`. Without it, a harness
that checked nothing would print AGREE on every line above and look exactly the same.

Two subtleties it covers:

**The state vocabularies do not match.** The spec has six states; the SDK's `Status` has five, and
they share only `COMPLETED` and `FAILED`. A condition sees neither directly — it reads
`state.results`, which Strands populates only once a node finishes. So `BLOCKED`, `READY`,
`IN_PROGRESS` and `CANCELED` all reach a condition as an *absent result*, and the predicate must
agree with that.

**An understated support set is caught.** A predicate reading a task outside its declared support
applies `st` outside its domain, and TLC reports it by name:

```
Error: Attempted to apply function:
to argument "b", which is not in the domain of the function.
```

## A complete worked example

```python
from anchor_conditions import all_complete

builder = GraphBuilder()
for name in ("research", "analysis", "factcheck", "report"):
    builder.add_node(agent(name), name)

builder.add_edge("research", "analysis")
builder.add_edge("research", "factcheck")
builder.add_edge("analysis",  "report", condition=all_complete("analysis", "factcheck"))
builder.add_edge("factcheck", "report", condition=all_complete("analysis", "factcheck"))
builder.set_entry_point("research")

graph = builder.build()
```

becomes

```tla
\* GENERATED by tests/strands/graph_to_tla.py from a live Strands Graph.
\* Do not edit. Regenerate instead.
------------------------------- MODULE Workflow -------------------------------

Tasks == {"analysis", "factcheck", "report", "research"}

Edges == {<<"analysis", "report">>, <<"factcheck", "report">>,
          <<"research", "analysis">>, <<"research", "factcheck">>}

EdgeCond(from, to, st) ==
    CASE <<from, to>> = <<"analysis", "report">>  -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] <<from, to>> = <<"factcheck", "report">> -> \A n \in {"analysis", "factcheck"} : st[n] = "COMPLETED"
      [] OTHER                                    -> TRUE

EdgeSupport(from, to) ==
    CASE <<from, to>> = <<"analysis", "report">>  -> {"analysis", "factcheck"}
      [] <<from, to>> = <<"factcheck", "report">> -> {"analysis", "factcheck"}
      [] OTHER                                    -> {}

NondetEdges == {}

=============================================================================
```

TLC then runs `DependencyDAG.tla` against it, exploring every order in which four agents could
succeed or fail, and reports that HP10 and termination hold.

The generated module is written into a **scratch directory**, never over the hand-written
`Workflow.tla` that the checked-in specs are verified against.

---

# What this model does not cover

Stated here rather than discovered later.

- **Re-execution.** Strands admits a node once per satisfied incoming edge, so it can run more than
  once. `COMPLETED` is terminal in this model, so a second run is outside it. `TerminalIsFinal` is a
  property of *this model*, not a claim about the SDK.
- **Skipping.** When no node is ready, the Strands execution loop simply ends. A node whose
  conditions never pass is never run, never appears in `results`, and the graph reports
  `Status.COMPLETED` — probed directly: `status=COMPLETED, ran ['plan', 'reject'], 2/3 nodes`. A
  workflow can silently drop part of its graph and still look successful. This model has no such
  state; `AllTerminate` is a property of the model, not of the runtime.
- **Cancellation.** `CancelOrphan` has **no counterpart in Strands at all.** The SDK's `Status` has
  no `CANCELED`, and a node failure fail-fasts the entire run rather than cancelling a subgraph. So
  Bug5's finding describes the *paper's* orchestrator; Strands satisfies neither half of it.
- **Time-varying conditions.** The tier-2 abstraction is "unknown but **fixed**" — `oracle` cannot
  flip mid-behaviour. A condition whose answer changes as the run progresses is not covered and needs
  a real predicate instead.
- **What a task actually does.** Agents appear only as `Succeed` or `Fail`. Nothing here says
  anything about their outputs being correct.
