------------------------------- MODULE ToolHook -------------------------------
(***************************************************************************)
(* A rate limit enforced in `before_tool_call`, under Strands' DEFAULT      *)
(* concurrent tool executor.                                                *)
(*                                                                          *)
(* THE SETTING, all of it read from the SDK source rather than assumed:      *)
(*                                                                          *)
(*   - `Agent.__init__` defaults to `ConcurrentToolExecutor()`.              *)
(*   - That executor does `asyncio.create_task(self._task(...))` once per    *)
(*     tool use in a batch, so every tool in one model turn runs as its own  *)
(*     task.                                                                 *)
(*   - Each task reaches `await ToolExecutor._invoke_before_tool_call_hook`  *)
(*     independently. So N copies of the hook body are in flight at once.    *)
(*   - `HookRegistry.invoke_callbacks_async` dispatches:                     *)
(*                                                                          *)
(*         if inspect.iscoroutinefunction(callback):                         *)
(*             await callback(event)     <- may suspend                      *)
(*         else:                                                             *)
(*             callback(event)           <- CANNOT suspend                   *)
(*                                                                          *)
(*   - The shipped `CedarAuthorization.before_tool_call` is a plain `def`    *)
(*     with no `await` in the whole 275-line file, so it takes the second    *)
(*     branch and its body runs to completion before any other tool task is  *)
(*     scheduled.                                                            *)
(*                                                                          *)
(* THE COUNTER. `_increment_call_count` is read-modify-write, and the        *)
(* resulting count is what the policy decides on:                            *)
(*                                                                          *)
(*     current    = self._call_counts.get(tool_name, 0)     <- READ          *)
(*     next_count = current + 1                                              *)
(*     self._call_counts[tool_name] = next_count            <- WRITE         *)
(*     ... cedarpy.is_authorized(..., call_count=next_count) <- DECIDE       *)
(*     ... self._decrement_call_count(...) on deny                           *)
(*                                                                          *)
(* THE POINT. That sequence is atomic, and nothing makes it atomic except    *)
(* the absence of an `await`. No lock, no documented guarantee, no comment.  *)
(* It is a property of the dispatch path, and it silently stops holding the  *)
(* moment the hook becomes `async def` -- which is what anyone does the      *)
(* first time the counter needs to live somewhere other than this process.   *)
(* The file's own docstring says counts are persisted to `agent.state` and   *)
(* warns they leak between agents that share a handler, so moving them to a  *)
(* shared store is the obvious next change, and it makes both the read and   *)
(* the write awaits.                                                         *)
(*                                                                          *)
(* WHERE THE SUSPENSION LANDS IS THE WHOLE QUESTION, which is why `Grain`    *)
(* has three values rather than a boolean. "An async hook is unsafe" is too  *)
(* crude to act on and this spec says so: one of the two split forms is      *)
(* still correct.                                                            *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Tools,      \* the tool calls in ONE batch -- each is its own asyncio task
    Limit,      \* the cap the policy enforces, as `call_count <= Limit`
    Grain       \* where the hook may suspend; see below

\* "atomic"      the shipped sync hook. Read, write and decide in one step,
\*               because a non-coroutine callback has no suspension point.
\* "readWrite"   an async hook that awaits BETWEEN reading the counter and
\*               writing it back -- a shared or persisted counter store.
\* "writeDecide" an async hook that awaits between writing the counter and
\*               deciding -- a remote policy engine, or an async enricher.
Grains == {"atomic", "readWrite", "writeDecide"}

ASSUME ToolHookAssumption ==
    /\ Tools # {}
    /\ Limit \in Nat
    /\ Grain \in Grains

VARIABLES
    count,      \* the shared counter, `self._call_counts[tool_name]`
    pc,         \* where each tool task has got to inside the hook body
    held,       \* what that task read out of the counter, before writing
    seen,       \* the count the policy decided on -- `next_count`
    proceeded   \* tasks whose hook returned Proceed, so the tool actually ran

vars == <<count, pc, held, seen, proceeded>>

Phases == {"ready", "read", "wrote", "done"}

TypeOK ==
    /\ count \in 0..Cardinality(Tools)
    /\ pc \in [Tools -> Phases]
    /\ held \in [Tools -> 0..Cardinality(Tools)]
    /\ seen \in [Tools -> 0..Cardinality(Tools)]
    /\ proceeded \subseteq Tools

Init ==
    /\ count = 0
    /\ pc = [t \in Tools |-> "ready"]
    /\ held = [t \in Tools |-> 0]
    /\ seen = [t \in Tools |-> 0]
    /\ proceeded = {}

(***************************************************************************)
(* The decision, shared by every grain. The policy is `call_count <= Limit` *)
(* evaluated on the count this task wrote. A deny gives the increment back, *)
(* which is what `_decrement_call_count` does.                              *)
(***************************************************************************)
Resolve(t, n) ==
    IF n <= Limit
    THEN /\ proceeded' = proceeded \union {t}
         /\ UNCHANGED count
    ELSE /\ count' = count - 1
         /\ UNCHANGED proceeded

(***************************************************************************)
(* THE SHIPPED HOOK. One step, because a synchronous callback cannot be     *)
(* interleaved -- asyncio is cooperative, and without a suspension point    *)
(* the task simply never yields.                                            *)
(***************************************************************************)
Atomic(t) ==
    /\ pc[t] = "ready"
    /\ LET n == count + 1
       IN /\ seen' = [seen EXCEPT ![t] = n]
          /\ IF n <= Limit
             THEN /\ count' = n
                  /\ proceeded' = proceeded \union {t}
             ELSE /\ UNCHANGED <<count, proceeded>>   \* +1 then -1
    /\ pc' = [pc EXCEPT ![t] = "done"]
    /\ UNCHANGED held

(***************************************************************************)
(* SPLIT AT THE READ. The classic lost update: two tasks read the same      *)
(* value, both write back one more than it, and the second write erases the *)
(* first. Both then decide on a count that is short by one.                 *)
(***************************************************************************)
Read(t) ==
    /\ pc[t] = "ready"
    /\ held' = [held EXCEPT ![t] = count]
    /\ pc' = [pc EXCEPT ![t] = "read"]
    /\ UNCHANGED <<count, seen, proceeded>>

WriteFromHeld(t) ==
    /\ pc[t] = "read"
    /\ count' = held[t] + 1
    /\ seen' = [seen EXCEPT ![t] = held[t] + 1]
    /\ pc' = [pc EXCEPT ![t] = "wrote"]
    /\ UNCHANGED <<held, proceeded>>

(***************************************************************************)
(* SPLIT AFTER THE WRITE. Read and write together -- no await inside        *)
(* `_increment_call_count` itself -- then suspend before deciding. This one *)
(* is SAFE, and saying so is the reason the spec has three grains: the      *)
(* counter still serializes, so each task decides on a distinct value.      *)
(***************************************************************************)
IncrementAtomically(t) ==
    /\ pc[t] = "ready"
    /\ count' = count + 1
    /\ seen' = [seen EXCEPT ![t] = count + 1]
    /\ pc' = [pc EXCEPT ![t] = "wrote"]
    /\ UNCHANGED <<held, proceeded>>

Decide(t) ==
    /\ pc[t] = "wrote"
    /\ Resolve(t, seen[t])
    /\ pc' = [pc EXCEPT ![t] = "done"]
    /\ UNCHANGED <<held, seen>>

Step(t) ==
    CASE Grain = "atomic"      -> Atomic(t)
      [] Grain = "readWrite"   -> Read(t) \/ WriteFromHeld(t) \/ Decide(t)
      [] Grain = "writeDecide" -> IncrementAtomically(t) \/ Decide(t)

Next == \E t \in Tools : Step(t)

\* No fairness needed. Every property here is a safety property, and the
\* violation is an interleaving rather than something failing to happen.
Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* THE PROPERTY                                                            *)
(*                                                                         *)
(* More tools ran than the cap allows. Note this counts what the HOOK let   *)
(* through, which is the only thing the hook controls.                      *)
(***************************************************************************)
CapRespected == Cardinality(proceeded) <= Limit

\* The counter should end up agreeing with reality: one increment per call
\* that was actually allowed. A lost update breaks this too, and it breaks it
\* PERMANENTLY -- the count is persisted to `agent.state`, so an
\* under-counted limiter stays under-counted for the rest of the session.
CounterHonest ==
    (\A t \in Tools : pc[t] = "done") => count = Cardinality(proceeded)

=============================================================================
