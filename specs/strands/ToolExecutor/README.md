# ToolExecutor

**A rate limit enforced in `before_tool_call`, under Strands' default concurrent tool executor.**

The shipped Cedar rate limiter is correct. It is correct for a reason nobody wrote down, that no
test covers and no comment mentions, and that stops being true the first time someone makes the
hook `async def` for an unrelated and entirely sensible reason.

| file | what it is |
|---|---|
| `ToolHook.tla` | the model: N concurrent tool tasks through one hook body |
| `ToolHook.cfg` | synchronous hook — the shipped behaviour. **Cap holds** |
| `AsyncHook_ReadWrite.cfg` | await between reading and writing the counter. **Cap violated** |
| `AsyncHook_WriteDecide.cfg` | await between writing and deciding. **Cap holds** |

New to TLA+? [`specs/strands/DependencyDAG/README.md`](../DependencyDAG/README.md) has a notation primer.

```bash
cd specs/strands/ToolExecutor && java -cp ../../lib/tla2tools-1.7.4.jar tlc2.TLC -cleanup \
    -config AsyncHook_ReadWrite.cfg ToolHook.tla
```

## What the SDK actually does

Every claim below is read from `strands-py/src/strands/`, not inferred.

**Tools in one batch run concurrently.** `Agent.__init__` ends with

```python
self.tool_executor = tool_executor or ConcurrentToolExecutor()
```

and that executor does `asyncio.create_task(self._task(...))` once per tool use. So when a model
turn returns three tool calls, three tasks run interleaved.

**Each task reaches the hook independently.** `_task` → `_stream_with_trace` → `_stream`, which
does `await ToolExecutor._invoke_before_tool_call_hook(...)`. N copies of your hook body are in
flight at once.

**And here is the line the whole thing rests on**, in `HookRegistry.invoke_callbacks_async`:

```python
if inspect.iscoroutinefunction(callback):
    await callback(event)      # may suspend
else:
    callback(event)            # cannot suspend
```

A plain `def` callback is **called, not awaited**. asyncio is cooperative: with no suspension point
inside it, the task cannot be preempted, so the body runs to completion before any other tool task
is scheduled. `CedarAuthorization.before_tool_call` is a plain `def`, and there is not one `await`
in the whole 275-line file.

**What it protects.** `_increment_call_count` is a read-modify-write whose result is the value the
policy decides on:

```python
current    = self._call_counts.get(tool_name, 0)      # READ
next_count = current + 1
self._call_counts[tool_name] = next_count             # WRITE
agent.state.set(_STATE_KEY, dict(self._call_counts))
# ... cedarpy.is_authorized(..., context={"session": {"call_count": next_count}})
# ... self._decrement_call_count(...) on deny
```

That sequence is atomic. Nothing makes it atomic except the absence of an `await` — no lock, no
documented guarantee, no comment. It is a property of the dispatch path, not of this file, and the
file cannot see it.

## Where the suspension lands is the whole question

"Async hooks are unsafe" would be easy to say and too crude to act on. One of the two async forms is
still correct, so the spec takes a `Grain` constant with three values rather than a boolean.

### `readWrite` — the finding

An await between reading the counter and writing it back. TLC's counterexample, with `Limit = 1`:

| step | what happens | `count` | tools let through |
|---|---|---|---|
| 1 | t1 and t2 both **read** 0 | 0 | — |
| 2 | t1 writes 1, decides 1 ≤ 1 → Proceed | 1 | t1 |
| 3 | t2 writes from its stale 0 → **1, not 2** | 1 | t1 |
| 4 | t2 decides 1 ≤ 1 → Proceed | 1 | **t1, t2** |

A cap of one let two calls through, and the policy is entirely correct — there is nothing in it to
fix. The counter is also left permanently short, which is the worse half: it is persisted to
`agent.state`, so an under-counted limiter stays under-counted for the rest of the session. That is
what `CounterHonest` checks.

**This is not a hypothetical refactor.** The handler's own docstring says counts are persisted to
`agent.state` and warns that *"multiple agents will cause rate-limit counts to leak between them."*
The obvious fix for that leak is to move the counter into a store the agents share — and a shared
store makes both the read and the write awaits. The change that fixes the documented bug introduces
the undocumented one.

### `writeDecide` — safe, and worth knowing

An await between writing the counter and deciding on it. This is where a suspension actually lands
if the policy engine is remote (an AgentCore Gateway call instead of local `cedarpy`) or the
`context_enricher` is async — so it is the case a reader is most likely to have.

It holds. The counter still serializes, so each task decides on a value no other task shares: t1
sees 1, t2 sees 2, and with `Limit = 1` the second is denied. The increment is a **reservation**,
not a check, and reserving before deciding is exactly what makes check-then-act safe.

That contrast is the actionable part. The rule is not "don't make hooks async". It is:

> **Keep the read and the write of any shared counter in one uninterrupted stretch.** Everything
> after the write can await freely.

### `atomic` — the control

A spec in which nothing can ever go wrong passes a safety check trivially and proves nothing. The
synchronous config is here so that the `readWrite` violation means something: the same model, the
same property, and the only difference is where the hook may suspend.

## The model, checked against a running agent

The three configs above are a model of code we read. This is the same three cases run through the
real SDK — a scripted model emitting four tool uses in one turn, the default executor, and one
`Limiter` whose body is identical in each. Only where it may suspend changes.

```bash
python tests/strands/tool_hook_probe.py
```
```
  hook                                     concurrent  count  allowed   verdict
  synchronous hook                                  1      4        1   cap holds
  async, suspends AFTER the write                   4      4        1   cap holds
  async, suspends BETWEEN read and write            4      1        4   CAP EXCEEDED / counter short
```

**The `concurrent` column is the load-bearing observation** — how many hook bodies were in flight
at once. A `def` callback never exceeds **one**, which is the atomicity claim measured rather than
argued: `invoke_callbacks_async` calls it instead of awaiting it, so no other tool task can be
scheduled inside it. The `async` ones reach four, so the batch really is concurrent and the
comparison is between like and like.

The last row is both spec properties failing together, exactly as `AsyncHook_ReadWrite.cfg`
predicts: `CapRespected` (a cap of one admitted four calls) and `CounterHonest` (the counter
recorded one). And the middle row is why the finding is stated as *"keep the read and the write in
one uninterrupted stretch"* rather than *"don't use async hooks"* — four bodies overlap there and
the cap still holds.

**A green run has to be earned.** Without overlap the unsafe case cannot lose an update, so the
probe measures the concurrency and fails loudly if the batch never overlapped, rather than
reporting a pass the setup could not have produced.

**What the probe does not add.** asyncio is cooperative, so the sync case is not *unlikely* to
interleave — it cannot, and no number of runs strengthens that. What it adds over the model is
that the SDK dispatches the way we read it, and that the lost update happens here rather than only
in TLA+.


## What this does not establish

- **It models the hook boundary, not Cedar.** The policy decision is `call_count <= Limit`, which
  stands in for whatever the real policy says. [`specs/policy/cedar`](../../policy/cedar) checks the decision itself
  and explicitly scopes the enforcement mechanism out; this is that missing half.
- **Three tools, one batch, one tool name.** The violation needs only two, and more tools cannot
  make a passing config fail — but the bound is real.
- **The `_decrement_call_count` path is modelled as giving the increment straight back.** The real
  one re-reads the dict, so under `readWrite` interleaving it has a lost-update window of its own.
  Not modelled, and it can only lose counts in the same direction.
- **No claim about `SequentialToolExecutor`.** It exists, and a workflow that selects it is not
  exposed to any of this. The finding is about the **default**.
- **~~Nothing here is validated against a running agent.~~** It is now:
  [`tests/strands/tool_hook_probe.py`](../../../tests/strands/tool_hook_probe.py) runs a real
  `Agent` with a scripted model that emits four tool uses in one turn, so the default
  `ConcurrentToolExecutor` spawns four tasks, and puts the same hook body through all three grains.
  See [below](#the-model-checked-against-a-running-agent).

## Why it belongs in this repo

The authorization work in [`specs/policy/TemporalPolicy`](../../policy/TemporalPolicy) asks whether a policy *says*
what its author meant. This asks whether the thing *enforcing* it does what the policy assumes. A
Dogwood aggregate cap and a Cedar `call_count` limit are the same shape — decide using a number that
shared state supplies — and a policy analyser cannot see the enforcement, by construction. Both
halves have to hold, and they fail independently.
