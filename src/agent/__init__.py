"""The agent that reviews policies, and the MCP wiring it reaches them through.

`policy_agent` is the whole surface: `anchor_server()` for the MCP client, `review()` to run one.
Kept separate from `translator` and `checker` because it is the only part that needs a MODEL, and
therefore the only part that cannot be tested without credentials and a bill.
"""

from __future__ import annotations

from .policy_agent import (SYSTEM_PROMPT, anchor_server, bedrock_api_key, build_model,
                           find_cli, gemini_api_key, review)

__all__ = ["SYSTEM_PROMPT", "anchor_server", "bedrock_api_key", "build_model", "find_cli",
           "gemini_api_key", "review"]
