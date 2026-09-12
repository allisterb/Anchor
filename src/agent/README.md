# `agent` — the part that talks to a person

[`checker`](../checker) answers precisely and narrowly: is this rule load-bearing, within this
bound, under this reading of history. None of that helps anyone unless the answer reaches them with
its qualifications attached. This is the part that talks to the person, and its job is **not to
overstate**.

```bash
python src/agent/policy_agent.py tests/policies/dead_forbid.dw
python src/agent/policy_agent.py a.dw --against b.dw
python src/agent/policy_agent.py firewall.dw --ask "does this let anything in from outside?"
```

It is a [Strands](https://github.com/strands-agents) agent whose tools are the
[`Anchor.MCPServer`](../Anchor.MCPServer) tools, reached by launching `anchor server` over stdio —
the same wiring an MCP host uses.

## The system prompt is thin, and that is the experiment

The server ships six knowledge articles saying what each verdict does and does not establish: that
VACUOUS is bounded by `attempts` rather than absolute, that a REFUSAL is not a clean result, that
`unknown` from a smoke run is never grounds for deleting a rule, that without an event schema every
answer assumes a reading which is not the deployed one.

Those articles were written for a model to read. **Until this agent existed, no model ever had.**

So the prompt does not restate them. It says the knowledge base exists and must be consulted before
a verdict is reported. Restating the caveats there would guarantee a well-qualified answer while
proving nothing about whether the knowledge base works — and the knowledge base is what an agent we
did not write would have to rely on.

If a review comes back missing the bound or the reading, that is a finding about the articles or the
tool descriptions. It is not a reason to thicken the prompt.

## The model is isolated, deliberately

A review needs credentials, a network call and a bill. Everything underneath it does not — and that
"everything" is where the mistakes actually live. So it is split:

| | needs a model? | what it proves |
|---|---|---|
| [`tests/strands/agent_wiring.py`](../../tests/strands/agent_wiring.py) | no | the server launches, every tool is advertised, every article is reachable both as a tool and as a resource, a real check runs, containment holds, a refusal is still a refusal — and Bedrock builds a client without reading `~/.aws`, signing with the bearer token, which is what keeps a native dependency out of the lock |
| `policy_agent.py` | yes | whether a model given only a thin prompt reports honestly |

That split earned itself immediately. Building the agent found a bug nothing else had: **`CheckPolicy`
hung forever over stdio** — five seconds over HTTP, never over stdio — because `PythonProcess` did
not redirect the child's stdin, so the checker inherited the MCP protocol pipe. Every test passed;
the transport every host actually uses was broken. See `AToolThatSpawnsAChildProcessAnswersOverStdio`.

## Configuration

| | |
|---|---|
| `ANCHOR_CLI` | path to `anchor.dll`. Otherwise a Release build is preferred, then Debug |
| `--project-dir` | the directory policy paths resolve inside; a path escaping it is refused. Defaults to the repo, and the agent is exactly the caller containment exists for |
| `--provider` | `auto`, `bedrock` or `gemini`. `auto` picks Gemini when a key is present and Bedrock otherwise — an API key in config was put there deliberately, whereas `~/.aws` exists on most machines whether or not the account can call a model |
| `--model` | model id. Defaults to the provider's own default |

## The model: Amazon or Google

Either **Amazon Bedrock** or **Google Gemini** — `--provider auto|bedrock|gemini`. Nothing else in
Anchor changes when you switch; only this last step needs an account.

Configuration, the setup each provider needs, and what each is verified to do live in one place:
**[`docs/model-providers.md`](../../docs/model-providers.md)**. The short version:

| | |
|---|---|
| Gemini | a key in `ApiKeys:GoogleAgentPlatform`. An *Agent Platform* key also needs the `Google` block — without it, `403 API_KEY_SERVICE_BLOCKED` |
| Bedrock | a bearer token in the environment (`AWS_BEARER_TOKEN_BEDROCK`), which `ApiKeys:AmazonBedrock` is put into for you, plus a **region** — with a key, `~/.aws` is not read, so nothing supplies one. Ordinary AWS credentials work too |

Two facts belong beside the code rather than in that document, because they are why
`build_bedrock_model` looks the way it does:

**botocore resolves the credential chain when the CLIENT is built** — before the bearer token is
consulted, and then discards it, because bearer auth supersedes SigV4 at signing. Walking the chain
can therefore only fail, never help. `keyed_session` points a scoped session at `os.devnull` for both
AWS config files when a key is present, which is what keeps `botocore[crt]` out of the dependency
list: the provider that needs it is never reached.

**`BedrockModel` refuses `region_name` beside `boto_session`.** A configured profile and a
configured region is an ordinary combination, so the region rides on the `Session`.

Copy [`appsettings.json.example`](appsettings.json.example) to `appsettings.json` here. It is
gitignored by `**/*appsettings.json`; the `.example` is not, because the pattern ends at `.json`.
