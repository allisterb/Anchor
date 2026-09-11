"""Does a real Strands agent behave the way `specs/strands/ToolExecutor` says?

That spec's claim, read out of the SDK source: a rate limit enforced in `before_tool_call` holds
only because a **synchronous** hook callback has no suspension point, while tools in one batch run
as concurrent asyncio tasks. Make the hook `async` with an `await` between the counter's read and
its write and the limit silently admits more calls.

Every other finding in this repo is checked against something that can disagree -- the Dogwood
corpus, the built engine, the real Cedar bindings. That one was backed only by reading three lines
of dispatch logic. This closes it: a running agent, a real `ConcurrentToolExecutor`, and the same
hook body written three ways.

    python tests/strands/tool_hook_probe.py

Needs the venv (`requirements/strands/install.cmd`). No network, no credentials, no AWS -- the
model is scripted, and it is scripted to emit SEVERAL tool uses in one turn, which is what makes
the executor spawn concurrent tasks at all.

WHAT IT DOES NOT SHOW. asyncio is cooperative, so the sync case is not "unlikely to interleave" --
it cannot, and no number of runs strengthens that. What the probe adds over the spec is that the
SDK really does dispatch the way we read it: that the batch is concurrent, that a `def` callback
runs to completion, and that an `await` between read and write does lose an update here rather
than only in the model.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]

from strands import Agent, tool  # noqa: E402
from strands.hooks import BeforeToolCallEvent  # noqa: E402
from strands.models import Model  # noqa: E402
from strands.types.content import Messages  # noqa: E402
from strands.types.event_loop import Usage  # noqa: E402
from strands.types.tools import ToolSpec  # noqa: E402

TOOLS = 4          # tool uses in one model turn -- one asyncio task each
LIMIT = 1          # the cap the "policy" enforces: call_count <= LIMIT


# ------------------------------------------------------------------------------------------------
# A model that asks for several tools at once. Without that there is one task and nothing to race.
# ------------------------------------------------------------------------------------------------
class MultiToolModel(Model):
    """Emits `TOOLS` tool uses in the first turn, then stops. No network, no credentials."""

    def __init__(self) -> None:
        self.turns = 0

    def get_config(self) -> Any:
        return {}

    def update_config(self, **model_config: Any) -> None:
        pass

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        tool_choice: Any | None = None,
        *,
        system_prompt_content=None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        self.turns += 1
        await asyncio.sleep(0)

        yield {"messageStart": {"role": "assistant"}}

        if self.turns == 1:
            # Several tool uses in ONE message. ConcurrentToolExecutor creates a task per use,
            # so this is what puts N copies of the hook body in flight together.
            for i in range(TOOLS):
                yield {"contentBlockStart":
                       {"start": {"toolUse": {"toolUseId": f"t{i}", "name": "work"}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": "{}"}}}}
                yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": "done"}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}

        yield {"metadata": {"usage": Usage(inputTokens=0, outputTokens=0, totalTokens=0),
                            "metrics": {"latencyMs": 0}}}


@tool
def work() -> str:
    """Does nothing; it exists to be called."""
    return "ok"


# ------------------------------------------------------------------------------------------------
# The limiter, written three ways. The BODY is the same in each: read, +1, write, decide.
# Only where it may suspend differs -- which is exactly the spec's `Grain`.
# ------------------------------------------------------------------------------------------------
class Limiter:
    def __init__(self) -> None:
        self.count = 0
        self.proceeded = 0
        self.observed_concurrent = 0      # how many hook bodies were in flight at once
        self._inside = 0


def sync_hook(state: Limiter):
    """`def` -- what CedarAuthorization ships. No suspension point anywhere in the body."""
    def hook(event: BeforeToolCallEvent) -> None:
        state._inside += 1
        state.observed_concurrent = max(state.observed_concurrent, state._inside)
        current = state.count
        nxt = current + 1
        state.count = nxt
        if nxt <= LIMIT:
            state.proceeded += 1
        state._inside -= 1
    return hook


def async_after_write_hook(state: Limiter):
    """`async def`, suspending AFTER the write -- a remote policy engine, or an async enricher.

    Safe. The counter still serialises, so every task decides on a value no other task shares.
    """
    async def hook(event: BeforeToolCallEvent) -> None:
        state._inside += 1
        state.observed_concurrent = max(state.observed_concurrent, state._inside)
        current = state.count
        nxt = current + 1
        state.count = nxt
        await asyncio.sleep(0)            # the decision is remote
        if nxt <= LIMIT:
            state.proceeded += 1
        state._inside -= 1
    return hook


def async_between_hook(state: Limiter):
    """`async def`, suspending BETWEEN the read and the write -- a shared counter store.

    The unsafe one, and not a contrived refactor: CedarAuthorization's own docstring says call
    counts are persisted to `agent.state` and warns they leak between agents sharing a handler.
    Moving that counter somewhere the agents share is the obvious fix, and it makes both the read
    and the write awaits.
    """
    async def hook(event: BeforeToolCallEvent) -> None:
        state._inside += 1
        state.observed_concurrent = max(state.observed_concurrent, state._inside)
        current = state.count
        await asyncio.sleep(0)            # the store is somewhere else
        nxt = current + 1
        state.count = nxt
        if nxt <= LIMIT:
            state.proceeded += 1
        state._inside -= 1
    return hook


async def run(make_hook) -> Limiter:
    state = Limiter()
    agent = Agent(model=MultiToolModel(), tools=[work], callback_handler=None,
                  hooks=[make_hook(state)])
    await agent.invoke_async("go")
    return state


CASES = [
    ("synchronous hook", sync_hook, True),
    ("async, suspends AFTER the write", async_after_write_hook, True),
    ("async, suspends BETWEEN read and write", async_between_hook, False),
]


def main() -> int:
    print(f"{TOOLS} tool uses in one turn, cap of {LIMIT}\n")
    print(f"  {'hook':40} {'concurrent':>10} {'count':>6} {'allowed':>8}   verdict")

    failures = 0
    for name, make_hook, expect_safe in CASES:
        state = asyncio.run(run(make_hook))

        # The cap is respected when no more calls were let through than it allows, and the
        # counter is honest when it recorded one increment per tool that ran.
        safe = state.proceeded <= LIMIT and state.count == TOOLS
        verdict = "cap holds" if safe else "CAP EXCEEDED / counter short"
        mark = "" if safe == expect_safe else "   ! NOT WHAT THE SPEC PREDICTS"
        failures += safe != expect_safe

        print(f"  {name:40} {state.observed_concurrent:>10} {state.count:>6} "
              f"{state.proceeded:>8}   {verdict}{mark}")

    print()
    if failures:
        print(f"{failures} case(s) where the running agent disagrees with "
              "specs/strands/ToolExecutor")
        return 1

    concurrent_seen = asyncio.run(run(async_between_hook)).observed_concurrent
    if concurrent_seen < 2:
        # Without overlap the unsafe case cannot lose an update, so a green run would mean
        # nothing. Fail loudly rather than reporting a pass the setup could not have earned.
        print(f"the batch never overlapped (max {concurrent_seen} hook body in flight), so "
              "nothing here was actually tested", file=sys.stderr)
        return 1

    print("the running agent behaves as specs/strands/ToolExecutor predicts: the batch is\n"
          "concurrent, a synchronous hook body cannot be interleaved, and an await between the\n"
          "counter's read and its write loses an update and admits more calls than the cap allows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
