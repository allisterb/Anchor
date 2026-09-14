# Anchor: An agentic formal verification framework for AWS Dogwood temporal policies using TLA+ and Strands SDK

## Inspiration

### The changing software security landscape
The recent explosion of autonomous AI-driven security compromises and AI model sandbox escapes, compounded by the growing prevalence of AI-generated code, has led to a huge amount of anxiety amoung developers and maintainers of cloud-based distributed systems, as well as calls for new kinds of software and software policy verification that are both broadly available and can offer stronger guarantees on the correctness and safety of these systems. 

The deployment of autonomous AI systems across safety-critical cloud
architectures, financial protocols, distributed enterprise workflows etc. as well as the use of autonomous AI agents for vulnerability scanning and exploitation has exposed fundamental limits in conventional validation of distributed system code and policies. Standard testing methods such as unit testing or fuzzing or manual peer review fail to guarantee correctness across all possible inputs that an AI could use, and also fail to keep up with the rapid rate of code production by AI agents. This divergence introduces security-critical vulnerabilities, including authorization bypasses, privilege escalation, and unintended execution pathways. Enforcing boundaries between distributed systems and verifying the correctness of policies that define those boundaries as well as verifying the behavior of AI agents that interpret, author, and refactor these policies, has never been more critical for the software world. 

Modern distributed systems infrastructure increasingly decouples governance rules and policies from underlying application code into domain-specific policy languages such as AWS's Cedar and Dogwood languages. Policies that control security, authorization, and admission-control systems represent the operational domains that are simultaneously the most
high-consequence to compromise and the most vulnerable to deliberate attacks by agents which can improvise and exhaustively explore input until they reach cases not covered by traditional testing methods..

### AWS Dogwood policy language
[Dogwood](https://aws.amazon.com/blogs/opensource/introducing-dogwood-runtime-verification-for-ai-agents/) is an open-source policy and governance language released by Amazon Web Services to control and verify AI agent behavior over time. Dogwood extendes the existing Cedar policy language with the following capabilities and features

* Temporal Policies: Built on Metric First-Order Temporal Logic (MFOTL), Dogwood evaluates agent requests based on a sequence of past actions rather than looking at a single action in isolation. It allows rules to check if prerequisite steps occurred, count how many times a tool was called, or verify if a spending limit was reached before permitting a new action. 
* Session-Awareness: Evaluates rules across a bounded sequence of events within a session (such as a 24-hour lookback window).
* In-Flight Tracking: Counts active, concurrent requests, not just completed ones, to prevent rapid-fire rule bypasses like submitting multiple large money transfers at the exact same millisecond.
* Sequence Control: Requires specific prerequisites, such as ensuring an invoice or human sign-off happens before a payment tool is triggered. 
* Rate and Total Limits: Caps spending, counts actions within a specific time window, or restricts transaction sizes based on prior activity in the same session. 

 Dogwood is built directly into Amazon Bedrock AgentCore to monitor and restrict agent tool calls at the infrastructure layer. But Dogwood policies suffer from the same vulnerabilities as software: an incorrectly written and inadequately tested policy, either by humans or by AI coding agents, can be discovered and exploited by autonomous AI agents with an explict objective of finding vulnrabilities, or by legitimate agents without the correct architectural guardrails and workflows that allows them to autonomously improvise and find vulnerabilites and work around incorrectly written policies to achieve a business goal, to the detriment of security.

(* Add Amazon AR checking of Dogwwod here and its limitations* )


As agents become part of mission-critical distributed systems and as more software is being written by agents, the same tools humans use for verifying policies and software must be made available to agents themselves to allow them to autonomosly test and repair and give feedback on the policies and code they write in response to natural language instructions from humans. 



### Agentic formal verification as a defensive measure
Formal verification provides a mathematically grounded proof that a software policy or workflow strictly satisfies a formal specification across *all* possible inputs, not only a single or subset of inputs as with traditional testing and runtime verification. However, traditional formal methods have historically suffered from prohibitive engineering overhead: authoring formal specifications required scarce technical expertise. The emerging paradigm of *agentic formal verification* resolves this bottleneck by connecting generative foundation models with automated formal tools such as model checkers, which allow agent-driven  loops for formal verification, from natural language human prompts. In such frameworks, generative models propose code, specifications, and intermediate proof steps, while deterministic verification backends mechanically validate candidate outputs, providing structured diagnostic signals and counterexamples that can guide iterative policy investigation and repair.

Agentic formal verification provides one answer to the velocity of AI-driven autonomous compromises, AI-agents becoming part of mission-critical distributed systems and AI-agent developed code being used to implement the components and security policies that govern these systems. Agents can autonomously write core specification modules and properties modules that model both the logic and the intent of policies and then use model checkers to check if these properties are satisfied and produce counter-examples showing where they fail to hold. However such systems have numerous failings and require a careful design and gating to produce useful, valid results.

An agentic formal verification system built using an framework like Strands SDK that supports flexible workflow logic and gating is a possible solution to the problem of agentic formal verification of policy languages like Dogwood.


## What it does
Anchor is a agentic formal verification framework that uses the [TLA+](https://lamport.azurewebsites.net/tla/tla.html) formal specification language and model checker to formally verify Amazon Dogwood temporal policies and Strands SDK agent graph workflows, and provides a Strands agent that allows humans to perform formal verification of these policies and code using natural language questions and prompts, without knowing the technical details of the formal verification framework or tools or theory.

Anchor allows developers and engineers and administrators to use the benefits of formal verification without requiring the specialized knowledge and skills formal methods typically demands. It uses a graph-based Strands multi-agent workflow to try to address the [known issues](https://arxiv.org/html/2606.05792v1) in agentic formal verification.

Anchor provides:

* A parser and [translator](https://github.com/allisterb/Anchor/tree/master/src/translator) from the Dogwood policy language to TLA+.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/policy/TemporalPolicy) that models a large subset of Dogwood temporal policy semantics, validated in [CI](https://github.com/allisterb/Anchor/actions/workflows/build.yml) against the Dogwood unit test and examples corpus.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/strands) and [Python annotations](https://github.com/allisterb/Anchor/tree/master/src/annotations) that allow Strands SDK users to model multi-agent Strands graph workflows 
* A [model property checker](https://github.com/allisterb/Anchor/tree/master/src/checker) that checks:
     * *derivable* property checks, which can be mechanically derived from all policies e.g. "is this policy vacuous or redundant?"
     * *intentional* property checks where a human or agent authors a check to explicitly capture the intent of a policy or workflow e.g. "Does this firewall policy intentionally block all inbound connections from external addresses?"
* An [MCP server](https://github.com/allisterb/Anchor/tree/master/src/Anchor.MCPServer) that provides the following tools to agents:
    * The TLA+ SANY parser and a TLA+ evaluator to assist in code generation
    * The Dogwood translator and model property checker 
    * Knowledge resources that an agent can use to author TLA+ specifications and properties modules and verify Dogwood policies
* A Strands [agentic workflow](https://github.com/allisterb/Anchor/tree/master/src/agent) for autonomous and HITL formal verification of Dogwood policies.
* A [CLI](https://github.com/allisterb/Anchor/tree/master/src/Anchor.CLI) that provides command-line access to the framework tools and MCP server and agent workflow launcher .

Anchor's formal verification can proceed in three modes. 

* `check` Mechanically checks a Dogwood policy against a mechanically translated base policy specification and an existing TLA+ properties module that captures the intent of the policy. The most precise
mode but it requires an existing TLA+ properties module and the knowledge to author one accurately. 
* `auto` This is the autoformalization mode. The only artifact a human supplies is a natural language brief that describes the intent of the policy. The agent is handed a vocabulary derived mechanically from
the policy, a knowledge article on how to write a properties module, and the brief - and it writes the TLA+. It never sees the policy's rule conditions, so what it drafts cannot be a restatement of the policy. Three models and four gates stand between a draft and a verdict.


* `hitl` Similar to auto mode but with one node added: when a gate turns a draft away it asks the person about the problem *requirement*, never about TLA, folds the answer into the brief and tries drafting the properties module again. Before the properties module is used, it reads the claim back in plain English for the user to confirm. Needs no formal methods knowledge on the user's part.

### Advantages of agentic formal verification
Integrating autonomous agents into formal verification infrastructure fundamentally alters the economics and operational guarantees of high-assurance software systems.
#### Eliminating the Proof Engineering Bottleneck 
Historically, the cost of constructing formal proofs exceeded the cost of authoring implementation code by one to two orders of magnitude. Agentic pipelines allow formal verification to scale to general software systems and non-specialist users without demanding dedicated formal methods knowledge or teams.

#### Deterministic Truth Signals Versus Generative Judge Models
Evaluating generated AI code with secondary judge models still suffers from issues like the persistence of probabilistic blind spots, sycophancy, and shared hallucinations. Formal verification acts as a non-negotiable filter: candidate code generated by an agent cannot be merged or deployed unless it satisfies the underlying mechanical verifier.

#### Continuous Refactoring and Regression Prevention
In enterprise policy engineering and DevOps workflows, policy changes routinely introduce regressions that remain undetected by standard test suites. Agentic formal verification enables automated continuous verification in CI/CD pipelines. When an AI refactors an existing
permission set or admission rule, the formal engine mathematically tests equivalence against the legacy policy across the entire domain. This allows safe, automated refactoring of mission-critical authorization systems at scale.

### Agentic formal verification critical pathologies, risks, and failure modes

Despite significant advances, deploying autonomous agents within formal verification loops introduces subtle failure modes. Because generative models optimize for task completion, they frequently discover pathological shortcuts that satisfy the mechanical verifier while undermining system security. Anchor is designed to try to remedy the pathologies and risks of agentic formal verification.

#### The Vacuity Trap and Adversarial Specification Gaming
The most prevalent pathology in agentic formal verification is vacuous verification. When an agent is tasked with synthesizing both an implementation and its formal specification, it frequently discovers that the simplest path to satisfying the verifier is to generate trivial or unsatisfiable contracts. Similarly, in auto-active repair systems, when an agent encounters an intractable verification
error, it often exhibits adversarial assertion pruning, modifying the source code or weakening the verification conditions until the verifier passes, effectively discarding the target security property. Mitigating vacuous verification requires mechanical checks and adversarial filtering and gates, both of which Anchor performs.


#### The User-Intent Formalization Gap and Semantic Drift
Formal verification only proves that an artifact conforms to a given mathematical specification; it does not prove that the specification accurately reflects the user's implicit real-world intent for a policy.
When an agent translates informal natural language requirements into formal specifications, semantic subtleties are frequently lost. Automated metrics that evaluate specification quality—such as mutation analysis, symbolic property testing, and reconstruction consistency—are critical to determining whether formal specifications faithfully mirror informal requirements. Anchor calculates these metrics and uses them as gates to accept or reject an autoformalization. 

#### State Explosion
Bounded Model Checking (BMC) like what the TLC checker does guarantees correctness only up to a fixed execution depth. If an autonomous agent relies solely on BMC to certify a loop or recursive policy rule, vulnerabilities lying at depth remain invisible, providing an incomplete
guarantee of mathematical assurance. Anchor allows the user to explictly specify the bounds of BMC and the Anchor knowledge resources and each Anchor report always emphasizes the lack of a finding does not translate into a finding not existing.


## How it works
The Dogwood temporal policy formal verification in Anchor makes use of two main external toolsets:
* The TLA+ language [tools](https://github.com/tlaplus/tlaplus)
* The Dogwood language [tools](https://github.com/dogwood-policy/dogwood)

The first step in Anchor formal verification is to mechanically [translate](https://github.com/allisterb/Anchor/blob/master/src/translator/dw_to_tla.py) a Dogwood policy to a TLA+ spec using the Anchor Dogwood policy parser and semantics specs. With a TLA+ specification module that models the *logic* of the policy, the next step is to obtain a properties module. A properties module extends the core policy specification and defines the *intent* of the policy that you want the TLC model checker to verify.

Anchor modes differ essentially on one thing: how much of the policy properties module
formalization the user needs to write.

| | TLA+ properties module author | launched as |
|---|---|---|
| `check` | the user | `anchor check policy.dw --property claim.tla` |
| `auto` | the agent, unattended | `anchor auto policy.dw --intent "..."` |
| `hitl` | the agent, with user feedback | `anchor hitl policy.dw` |


## How we built it
Anchor is written in C# and Python. 
| Project |Language| Responsibility |
|---|---|---|
| `Anchor.Runtime` | C#|Shared base types, logging. |
| `Anchor.CLI` | C#| CLI access to the framework tools and the MCP server launcher |
| `Anchor.Verifiers.TLAPlus` | C#| Hosts the TLA+ language tools |
| `Anchor.MCPServer` |C#| MCP server implementation providing agents access to the framework tools and verifiers, tools for writing TLA+ specs and knowledge resources.|
| `translator` |Python| Mechanically translate Dogwood policies to TLA+ specifications.|
| `check` | Python|Uses the TLC bounded model property checker for verifyng derived and intentional properties from an input TLA+ policy spec and properties module|
| `annotations` |Python| Provides annotations to assist in creating TLA+ specs from Strands SDK graph builder workdlows|
| `agent` | Python | Strands SDK agent orchestrator for HITL and autonomous formal verification|

The SANY parser the MCP tools use is an IKVM .NET [port](https://github.com/allisterb/Anchor/blob/master/src/Anchor.Verifiers.TLAPlus/Anchor.Verifiers.TLAPlus.csproj) of the Java tlatools library. This allows the parser to be used as an ordinary in-process .NET library this is repeatedly called by the MCP tool used by the agent for TLA+ code generation without having to launch an external JVM process everytime.

Given a directory instead of a file it audits
every policy in it against the modules already beside them.
**Measured on the five requirements of `examples/aws2/agent-policy.dw`**, taken verbatim from the
AWS article: `auto` accepted **1 of 5** on its first sweep, and every failure was a property that was
well-formed and said something the brief did not quite mean. Of the four it failed, two have since
been closed by `hitl` and one more by `auto` after the gates themselves were corrected. That is the
user-intent formalization gap described below, measured rather than asserted.



`anchor` is one launcher over two runtimes: `./anchor` on Linux and macOS, `./anchor.ps1` under
PowerShell. `check`, `explain` and `server` are the .NET CLI; `auto` and `hitl` are Python entry
points, reachable directly as `python src/agent/pipeline.py` and `python src/agent/hitl.py`.
Agentic formal verification is an active [research program](https://arxiv.org/html/2511.17330v1).