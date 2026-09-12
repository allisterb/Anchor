"""An agent that reviews authorization policies, and reports what was actually established.

    python src/agent/policy_agent.py tests/policies/dead_forbid.dw
    python src/agent/policy_agent.py a.dw --against b.dw

WHAT IT IS FOR. Everything else in this repository answers a question precisely and narrowly: is
this rule load-bearing, within this bound, under this reading of history. None of that is useful to
a person unless the answer reaches them with its qualifications attached. The agent is the part that
talks to the person, and its job is not to be persuasive -- it is to not overstate.

THE SYSTEM PROMPT IS DELIBERATELY THIN, AND THAT IS THE EXPERIMENT.

`Anchor.MCPServer` ships six knowledge articles saying what each verdict does and does not mean: that
VACUOUS is bounded by `attempts` rather than absolute, that a REFUSAL is not a clean result, that
`unknown` from a smoke run is never grounds for deleting a rule, that without an event schema every
answer assumes a reading which is not the deployed one. Those articles were written for a model to
read, and until this file existed no model had ever read one.

So the prompt below does not restate them. It says the knowledge base exists and must be consulted
before a verdict is reported. Restating the caveats here would guarantee a well-qualified answer
while proving nothing about whether the knowledge base works -- and the knowledge base is what an
agent we did not write would have to rely on.

If a review comes back missing the bound or the reading, that is a finding about the articles or
the tool descriptions, not a reason to thicken this prompt.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SYSTEM_PROMPT = """\
You review authorization policies for someone who has to act on your answer.

Your tools model-check a Dogwood (.dw) policy: they report, rule by rule, whether each one is
load-bearing. They also expose a knowledge base describing what those answers do and do not
establish.

BEFORE YOU REPORT ANY VERDICT, read the knowledge-base article covering it. The tools answer
bounded questions; the articles say what the bounds are. A verdict repeated without them claims
more than was checked.

Report what was established and nothing more. If the checker declined to answer, say so and say
why -- that is not a clean result. If you are unsure whether something was established, say that
too; an honest gap is worth more here than a confident summary.
"""


def find_cli() -> Path:
    """The built `anchor` binary this agent launches as its MCP server.

    Release before Debug, since a Release tree is the deliberate one. `ANCHOR_CLI` overrides both,
    which is how a container points at wherever it installed the binary.
    """
    if (override := os.environ.get("ANCHOR_CLI")):
        return Path(override)

    for configuration in ("Release", "Debug"):
        candidate = REPO / "src" / "Anchor.CLI" / "bin" / configuration / "net10.0" / "anchor.dll"
        if candidate.exists():
            return candidate

    raise SystemExit(
        "the anchor CLI is not built. Run:\n"
        "    dotnet build Anchor.sln\n"
        "or set ANCHOR_CLI to the path of anchor.dll")


def anchor_server(project_dir: Path | None = None):
    """An MCP client speaking to `anchor server` over stdio.

    Launched as a child process, which is the wiring an MCP host uses and therefore the wiring worth
    exercising. `--project-dir` is passed so that every path the agent names is resolved inside the
    tree and one escaping it is refused -- the agent is exactly the caller that containment exists
    for.
    """
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    root = str(project_dir or REPO)
    params = StdioServerParameters(
        command="dotnet",
        args=[str(find_cli()), "server", "--project-dir", root],
        cwd=root)

    return MCPClient(lambda: stdio_client(params))


GEMINI_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# The same setting name Polson uses, so one convention covers both. Colon-delimited, which is the
# .NET configuration spelling for nesting: {"ApiKeys": {"GoogleAgentPlatform": "..."}}.
GEMINI_SETTING = "ApiKeys:GoogleAgentPlatform"


def appsettings_path() -> Path | None:
    """The development settings file, if there is one.

    `ANCHOR_APPSETTINGS` first, so a container can point at a file it wrote from a secret store;
    then beside this module, which is where a developer puts it; then the repository root.

    Every one of these is gitignored by `**/*appsettings.json`. That is checked rather than assumed,
    because the whole point of the file is that it holds a key.
    """
    if (override := os.environ.get("ANCHOR_APPSETTINGS")):
        return Path(override) if Path(override).exists() else None

    for candidate in (Path(__file__).resolve().parent / "appsettings.json",
                      REPO / "appsettings.json"):
        if candidate.exists():
            return candidate
    return None


def setting(name: str) -> str | None:
    """One colon-delimited setting, or None. Never raises on a bad file, and never logs a value."""
    path = appsettings_path()
    if path is None:
        return None

    try:
        # utf-8-sig: a file written by a Windows editor routinely carries a BOM, and json.loads
        # rejects one.
        import json
        node = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        # The path and the failure, never the contents: this file exists to hold a secret, so a
        # parse error must not print it back out in a diagnostic.
        print(f"warning: could not read {path}: {type(e).__name__}", file=sys.stderr)
        return None

    for part in name.split(":"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]

    return node if isinstance(node, str) and node.strip() else None


def setting_raw(name: str):
    """A setting of any type. `setting` is the string-only form and is what most callers want."""
    path = appsettings_path()
    if path is None:
        return None

    try:
        import json
        node = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None

    for part in name.split(":"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def gemini_client_args() -> dict:
    """Arguments for the underlying `genai.Client`.

    A key alone reaches the public Developer API at `generativelanguage.googleapis.com`. An Agent
    Platform key does not work there -- it comes back 403 `API_KEY_SERVICE_BLOCKED`, which names the
    API rather than the mistake -- and needs `enterprise=True` with a project and location instead.
    Which one you have is a property of the key, not something worth guessing, so it is configured.

    Environment before file, as everywhere else here: a deployment injects, a developer edits.
    """
    args: dict = {}

    if (key := gemini_api_key()):
        args["api_key"] = key

    # The names google-genai reads itself, so a container that already sets them needs nothing else.
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or setting("Google:Project")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or setting("Google:Location")

    if project:
        args["project"] = project
    if location:
        args["location"] = location

    enterprise = os.environ.get("GOOGLE_GENAI_ENTERPRISE") or setting_raw("Google:Enterprise")
    if enterprise in (True, "true", "True", "1"):
        args["enterprise"] = True

    return args


def gemini_api_key() -> str | None:
    """The Gemini key, from the environment or from appsettings.json.

    Environment first. Not because it is the nicer way to work -- on Windows it is markedly worse,
    which is why the file exists -- but because a deployment injects one, and an injected secret
    should win over a file that happened to come along for the ride.
    """
    for name in GEMINI_KEYS:
        if os.environ.get(name):
            return os.environ[name]

    return setting(GEMINI_SETTING)


def build_model(provider: str = "auto", model_id: str | None = None):
    """The model to reason with, or None for the Strands default.

    `auto` picks Gemini when an API key is in the environment and Bedrock otherwise. That ordering
    is not a preference between them: a key that is present was put there deliberately, whereas
    Bedrock credentials sit in `~/.aws` on most machines whether or not the account can actually
    call a model. Preferring the explicit signal fails less confusingly.
    """
    if provider == "auto":
        provider = "gemini" if gemini_api_key() else "bedrock"

    if provider == "bedrock":
        # A bare string is a Bedrock model id to Strands, and None means its own default.
        return model_id

    if provider != "gemini":
        raise SystemExit(f"unknown provider {provider!r}; expected 'bedrock', 'gemini' or 'auto'")

    try:
        from strands.models.gemini import GeminiModel
    except ImportError as e:
        # The provider MODULE ships with strands-agents; only the SDK underneath it is missing, so
        # say which one rather than letting "No module named 'google'" stand as the explanation.
        raise SystemExit(
            f"the Gemini provider needs the google-genai SDK, which is not installed ({e}).\n"
            "It is a pinned dependency like every other: add it to requirements/strands/"
            "requirements.in, recompile the lock, and install by hand. See requirements/README.md."
        ) from e

    args = gemini_client_args()
    if "api_key" not in args:
        raise SystemExit(
            "no Gemini API key. Put one in an appsettings.json beside src/agent/ (or at the repo "
            f'root) as {{"ApiKeys": {{"GoogleAgentPlatform": "..."}}}}, or set one of '
            f"{' or '.join(GEMINI_KEYS)}. See src/agent/appsettings.json.example.")

    if args.get("enterprise") and not args.get("project"):
        raise SystemExit(
            "Google:Enterprise is set but Google:Project is not. An Agent Platform key needs a "
            "project and a location; see src/agent/appsettings.json.example.")

    return GeminiModel(client_args=args, model_id=model_id or DEFAULT_GEMINI_MODEL)


def review(request: str, project_dir: Path | None = None, model: str | None = None,
           provider: str = "auto") -> str:
    """Run one review. Returns what the agent said."""
    from strands import Agent

    client = anchor_server(project_dir)
    with client:
        tools = client.list_tools_sync()
        # callback_handler=None turns off Strands' default printer. Left on, it streams the answer
        # to stdout as it is generated AND we print the returned result, so the review arrives
        # twice — which reads as a bug in the checker rather than in the plumbing.
        agent = Agent(model=build_model(provider, model), tools=tools,
                      system_prompt=SYSTEM_PROMPT, callback_handler=None)
        return str(agent(request))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("policy", type=str, help="a .dw policy file, relative to the project directory")
    ap.add_argument("--against", type=str, help="a second .dw file to compare against")
    ap.add_argument("--event-schema", type=str, help="the .dwschema the policy is deployed under")
    ap.add_argument("--project-dir", type=Path, default=REPO,
                    help="the directory policy paths are resolved inside (default: the repo)")
    ap.add_argument("--provider", type=str, default="auto",
                    choices=("auto", "bedrock", "gemini"),
                    help="which model provider. `auto` picks gemini when GEMINI_API_KEY or "
                         "GOOGLE_API_KEY is set, and bedrock otherwise")
    ap.add_argument("--model", type=str, default=None,
                    help="model id; defaults to the provider's own default")
    ap.add_argument("--ask", type=str, default=None,
                    help="ask something else about the policy instead of the standard review")
    args = ap.parse_args()

    if args.ask:
        request = f"{args.ask}\n\nThe policy file is {args.policy}."
    else:
        request = (f"Review the policy at {args.policy}. Tell me whether every rule in it is doing "
                   f"something, and what I should be aware of about the answer.")
        if args.against:
            request += f" Compare it against {args.against}."
        if args.event_schema:
            request += f" It is deployed under the event schema {args.event_schema}."

    # A live model call, which costs money and reaches the network. Said plainly rather than
    # discovered on the bill.
    print(f"asking the model to review {args.policy} (this makes live model calls)\n",
          file=sys.stderr)

    print(review(request, args.project_dir, args.model, args.provider))
    return 0


if __name__ == "__main__":
    sys.exit(main())
