"""The AgentCore Runtime contract, wrapping the policy agent.

    python src/agent/server.py                 # or: uvicorn agent.server:app --host 0.0.0.0 --port 8080

Bedrock AgentCore requires a container to expose exactly two endpoints on port 8080:

    POST /invocations   {"input": {"prompt": "..."}}  ->  {"output": {...}}
    GET  /ping          ->  {"status": "healthy"}

and to be built for linux/arm64. That is the whole contract; everything else about the agent is
ours.

STARLETTE, NOT FASTAPI, and the reason is the supply chain rather than taste. AWS's example uses
FastAPI; it is not installed here, and adding it would mean another pass through a hash-locked
requirements file for two routes and a JSON body. `starlette` and `uvicorn` are already present --
`mcp` pulls them in, which `requirements/strands/requirements.in` already notes -- so this costs no
new dependency at all.

THE REVIEW IS RUN IN A THREADPOOL. `review()` launches the MCP server as a child process and blocks
on it; called directly from an async handler it would stall the event loop, and `/ping` would start
failing health checks for the duration of somebody else's model check.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from starlette.applications import Starlette          # noqa: E402
from starlette.concurrency import run_in_threadpool   # noqa: E402
from starlette.requests import Request                # noqa: E402
from starlette.responses import JSONResponse          # noqa: E402
from starlette.routing import Route                   # noqa: E402

from agent.policy_agent import explain, review        # noqa: E402


async def ping(_: Request) -> JSONResponse:
    """Liveness. Deliberately answers without touching the model, the toolchain or a session.

    A health check that exercised the checker would report the container unhealthy whenever a long
    model check was in flight, which is exactly when it is most working.
    """
    return JSONResponse({"status": "healthy"})


async def invocations(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "body must be JSON"}, status_code=400)

    payload = body.get("input") if isinstance(body, dict) else None
    if not isinstance(payload, dict):
        return JSONResponse({"error": "expected {\"input\": {...}}"}, status_code=400)

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse({"error": "'prompt' must be a non-empty string"}, status_code=400)

    try:
        answer = await run_in_threadpool(review, prompt, PROJECT_DIR)
    except Exception as e:                                    # noqa: BLE001
        # LOG IT AS WELL AS RETURNING IT, which is not belt and braces -- it is the only way the
        # detail survives. AgentCore replaces a 500 body with "Received error (500) from runtime.
        # Please check your CloudWatch logs", so a handler that only returns the reason produces a
        # failure that reaches neither the caller nor the logs. Found exactly that way.
        traceback.print_exc(file=sys.stderr)
        if (meaning := explain(e)) is not None:
            print(f"the model refused: {e}\n\n{meaning}", file=sys.stderr, flush=True)

        # The type and message, never a traceback: a stack trace across this boundary tells a
        # caller about our filesystem and nothing about their request. The traceback went to the
        # log above, where it belongs.
        body = {"error": f"the review failed: {type(e).__name__}: {e}"}
        if meaning is not None:
            body["meaning"] = meaning
        return JSONResponse(body, status_code=500)

    return JSONResponse({"output": {
        "message": answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }})


# The directory policy paths resolve inside. Containment matters more here than anywhere else in the
# project: the caller is remote, and the checker prints the policy it read.
PROJECT_DIR = Path(os.environ.get("ANCHOR_PROJECT_DIR", REPO))

app = Starlette(routes=[
    Route("/invocations", invocations, methods=["POST"]),
    Route("/ping", ping, methods=["GET"]),
])


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0, not the loopback: a container binding the loopback accepts nothing from outside
    # itself, which presents as a health check that never passes on a server that looks fine from a
    # shell inside the same container.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
