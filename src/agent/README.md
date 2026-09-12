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
| [`tests/strands/agent_wiring.py`](../../tests/strands/agent_wiring.py) | no | the server launches, every tool is advertised, every article is reachable both as a tool and as a resource, a real check runs, containment holds, a refusal is still a refusal |
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
| `--model` | model id. Defaults to the Strands default, which is Bedrock and needs AWS credentials |
