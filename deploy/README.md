# `deploy` — Anchor on Bedrock AgentCore

AgentCore's contract is short, and all of it is mandatory:

| | |
|---|---|
| platform | `linux/arm64` |
| port | 8080 |
| endpoints | `POST /invocations`, `GET /ping` |
| registry | the image must live in ECR |

`src/agent/server.py` is our side of it — two routes on Starlette. AWS's example uses FastAPI; that
is not installed here and adding it would mean another pass through a hash-locked requirements file
for two routes and a JSON body. `starlette` and `uvicorn` arrive with `mcp` already.

## What the image carries, and what it does not

| in | why |
|---|---|
| the `anchor` CLI | the MCP server the agent talks to. Published **self-contained**, so no .NET runtime is installed |
| a headless JRE | TLC is a real JVM program; IKVM cannot run it in-process |
| `tla2tools.jar` | architecture-neutral bytecode, fetched and digest-checked at build time |
| CPython 3.13 | the translator, the checker, and the agent |

**Not** in the image: Rust and the Dogwood binary. The runtime path references Dogwood only in
comments — it is the differential *test* oracle, and tests do not ship. That was originally called
out as the main ARM64 risk, a slow Rust build under emulation; checking rather than assuming removed
it entirely.

## Five things that had to change, four of them only findable by running it

**`RuntimeIdentifiers` is declared repo-wide** in `Directory.Build.props`. Publishing for
`linux-arm64` adds a `net10.0/linux-arm64` section to every lock file — IKVM and `System.Data.Odbc`
resolve per-RID — and a locked restore inside the image fails with `NU1004` if that section is not
already committed. Setting it on `Anchor.CLI` alone was not enough: the RID propagates through every
`ProjectReference`, and the failure named `Anchor.Runtime`, `Anchor.Verifiers.TLAPlus` and
`Anchor.MCPServer`, none of which mention a RID themselves.

**The agent launches the CLI two ways.** A framework-dependent build is a `.dll` that `dotnet` runs;
the self-contained publish in the image is a native executable that runs itself. `anchor_server()`
tells them apart by suffix, because getting it wrong produces "cannot execute binary file" rather
than anything about the build.

**libicu is not optional.** A slim Python image has no ICU, and the self-contained `anchor` binary
dies at startup with "Couldn't find a valid ICU package installed on the system". The cheaper fix,
`InvariantGlobalization`, is the wrong one: it silently changes culture-sensitive string behaviour,
so the container would differ from every developer machine in ways nothing reports.

**The publish output is a directory, not a file.** `-o /out/cli` emits 363 files and the executable
is one of them. `COPY /out/anchor /app/anchor` made `/app/anchor` a directory, `ANCHOR_CLI` named it,
and the first MCP call failed with "is a directory: permission denied".

**`ANCHOR_ROOT` does not reach the MCP server on its own.** `stdio_client` passes a scrubbed
allow-list to servers it launches -- PATH, HOME, TEMP and a few more -- rather than inheriting the
environment. That is a good default: it stops a server we launch from reading the API key we hold.
It also drops `ANCHOR_ROOT`, and in a checkout nothing looks wrong because the server falls back to
walking up to `Anchor.sln`. In the image there is no solution file, so every tool call returned "No
Anchor tree found" -- reported honestly by the agent, which said it could not review anything.
`anchor_server()` extends the allow-list by exactly that one entry.

## Build

The .NET stage runs on `$BUILDPLATFORM` and **cross-compiles**, so the C# build never goes through
QEMU. Only the Python stage is emulated.

```bash
docker buildx build --platform linux/arm64 -f deploy/Dockerfile -t anchor:arm64 --load .
docker run --platform linux/arm64 -p 8080:8080 -e GEMINI_API_KEY=... anchor:arm64
```

```bash
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input": {"prompt": "Review tests/policies/dead_forbid.dw"}}'
```

## Push and deploy

```bash
aws ecr create-repository --repository-name anchor --region <region>
aws ecr get-login-password --region <region> \
  | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

docker buildx build --platform linux/arm64 -f deploy/Dockerfile \
  -t <account>.dkr.ecr.<region>.amazonaws.com/anchor:latest --push .

aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name anchor \
  --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"<account>.dkr.ecr.<region>.amazonaws.com/anchor:latest"}}' \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --protocol-configuration '{"serverProtocol":"HTTP"}' \
  --role-arn arn:aws:iam::<account>:role/<AgentRuntimeRole> \
  --environment-variables '{"GEMINI_API_KEY":"..."}'
```

Then `aws bedrock-agentcore invoke-agent-runtime`. The session id must be **33 characters or more**.

### The key

Inject it; never bake it. `.dockerignore` excludes `**/appsettings.json` by its own pattern before
anything else, because a key in a layer is a key published to everyone who can pull the image. The
agent reads the environment before the file for exactly this reason — a deployment injects, a
developer edits.

`--environment-variables` above is the simplest form. A secret store is better, and the agent needs
no change for it: anything that puts `GEMINI_API_KEY` in the process environment works.

## The other deployment, which is one flag away

`serverProtocol` also accepts **`MCP`**. That deploys the MCP server itself rather than the agent —
AgentCore hosts the tools, and a caller brings their own model. It needs no API key in the container
at all, and the image already contains everything for it: the CMD becomes
`/app/cli/anchor server --http --port 8080`.

Worth knowing because the two answer different questions. `HTTP` gives a judge a URL that returns a
policy review; `MCP` gives any agent formally-checked policy tools. The image is the same.
