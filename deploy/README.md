# Deploying to Bedrock AgentCore Runtime

The agent packaged as a container and run by AWS. [`Dockerfile`](Dockerfile) is the image,
[`iam/`](iam) is the execution role, [`render.py`](render.py) fills in the account-specific parts.

Everything below uses `<account-id>`, `<region>`, `<ecr-repo>` and `<agent-name>` rather than real
values. Substitute your own, or let `render.py` read the account from your current credentials.

```bash
export ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export REGION=<region>
export REPO=<ecr-repo>
export AGENT=<agent-name>
```

## What is in the image, and why it is bigger than an agent usually is

| | |
|---|---|
| the `anchor` CLI | the MCP server the agent talks to, published self-contained so no .NET runtime is needed |
| a JVM | TLC is the model checker and it is a real JVM — IKVM cannot run it in-process |
| `tla2tools.jar` | the TLA+ tools; architecture-neutral bytecode |
| CPython | the translator, the checker, and the agent itself |

**Not** in it: Rust and the Dogwood binary. The runtime path references Dogwood only in comments —
it is the differential *test* oracle, and tests do not ship. That removed the slowest and least
predictable part of an emulated arm64 build.

Two things in the Dockerfile look like overhead and are not. `libicu72` is required: a slim Python
image has no ICU and the self-contained binary dies at startup without it. The alternative,
`InvariantGlobalization`, is smaller and *wrong* — it silently changes culture-sensitive string
behaviour, so the container would differ from every developer machine in ways nothing reports.

## 1. Build

AgentCore requires `linux/arm64`. The .NET stage runs on `$BUILDPLATFORM` and cross-compiles, so
only the Python layers are emulated.

```bash
docker buildx build --platform linux/arm64 -f deploy/Dockerfile \
  -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest --load .
```

**Check that no secret went in.** [`.dockerignore`](../.dockerignore) excludes `**/appsettings.json`
as its first entry, because a key baked into a layer is a key published to anyone who can pull the
image. Verify rather than trust:

```bash
docker run --rm --entrypoint sh $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest \
  -c 'find / -name "appsettings*.json" -not -path "*/dotnet/*" 2>/dev/null; echo "(end)"'
```

## 2. Push

```bash
aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
```

## 3. The execution role

AgentCore assumes a role to run the container. The trust policy names
`bedrock-agentcore.amazonaws.com` and is conditioned on your account and region, so another
account's AgentCore cannot assume it.

```bash
python deploy/render.py trust-policy     --region $REGION --agent-name $AGENT -o /tmp/trust.json
python deploy/render.py execution-policy --region $REGION --agent-name $AGENT --ecr-repo $REPO -o /tmp/exec.json

aws iam create-role --role-name AmazonBedrockAgentCoreRuntime$AGENT \
  --assume-role-policy-document file:///tmp/trust.json
aws iam put-role-policy --role-name AmazonBedrockAgentCoreRuntime$AGENT \
  --policy-name ${AGENT}AgentCoreRuntimeExecution --policy-document file:///tmp/exec.json
```

Two deliberate narrowings against the policy AWS documents:

- **ECR is scoped to the one repository**, not `repository/*`. The role needs to pull one image.
- **`GetWorkloadAccessTokenForUserId` is omitted.** AWS's own guidance is to deny it outside
  development: it issues workload tokens from a caller-supplied user id with no IdP verification.
  `GetWorkloadAccessTokenForJWT` is kept.

## 4. Create the runtime

```bash
aws bedrock-agentcore-control create-agent-runtime --region $REGION \
  --agent-runtime-name $AGENT \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest\"}}" \
  --role-arn arn:aws:iam::$ACCOUNT:role/AmazonBedrockAgentCoreRuntime$AGENT \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --protocol-configuration '{"serverProtocol":"HTTP"}'
```

`serverProtocol` is **HTTP**, not MCP. The container speaks the AgentCore contract —
`POST /invocations`, `GET /ping` — and the MCP server lives *inside* it, launched over stdio as a
child process. Declaring MCP here would advertise a protocol the container does not speak on 8080.

## 5. Invoke

```bash
echo '{"input":{"prompt":"Review the policy at tests/policies/dead_forbid.dw"}}' > /tmp/payload.json

aws bedrock-agentcore invoke-agent-runtime --region $REGION \
  --cli-binary-format raw-in-base64-out --cli-read-timeout 600 \
  --agent-runtime-arn arn:aws:bedrock-agentcore:$REGION:$ACCOUNT:runtime/<runtime-id> \
  --payload file:///tmp/payload.json --content-type application/json \
  /tmp/response.json
```

**Both flags are needed and neither is obvious.** Without `--cli-binary-format raw-in-base64-out`
the CLI expects the payload to be base64 already and rejects plain JSON as *"Invalid base64"*.
Without `--cli-read-timeout` the default 60 seconds expires long before a check involving a JVM,
TLC and a model call — and that timeout looks like a hung agent rather than an impatient client.

## Traps worth knowing

**A 500 does not reach you.** AgentCore replaces the response body with *"Received error (500) from
runtime. Please check your CloudWatch logs for more information."* — so a handler that returns its
reason without logging it produces a failure that reaches neither the caller nor the log. Found
exactly that way; `server.py` now logs the traceback and the classified explanation before
returning. If you add a failure path, log it.

**`CreateOAuth2Token ... invalid, expired, revoked, or malformed`** from the control plane, while
`aws sts get-caller-identity` succeeds, has been transient. Retry before investigating: it recovered
on its own after a couple of minutes here, with nothing about the role or the runtime changed.

**The image tag is resolved when the runtime is created or updated**, not per session. Pushing a new
`:latest` changes nothing until `update-agent-runtime` is called, which cuts a new version.

## Credentials inside the container

**No API key needs to reach AWS.** With no key configured, `build_bedrock_model` falls through to
ordinary credential resolution, which in a container is the task role — the execution role above,
which carries `bedrock:InvokeModel`. `AWS_REGION` is set by the runtime.

That is why the image ships no key and why `.dockerignore` excludes `appsettings.json`: the
deployed path authenticates by role, and the key is a *developer-machine* convenience.

Using Gemini instead would mean putting a key in `--environment-variables`, where it is readable by
anyone with `GetAgentRuntime`. Prefer the role.

## Logs

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime-id>-DEFAULT --region $REGION --follow
```
