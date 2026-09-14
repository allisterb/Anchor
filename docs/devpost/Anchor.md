# Anchor: An agentic formal verification framework for Amazon Dogwood policies and Strands SDK graph workflows

## Inspiration
The recent explosion of autonomous AI-driven security compromises and AI model sandbox escapes, compounded by the growing prevalence of AI-generated code, has led to a huge amount of anxiety amoung developers and maintainers of cloud-based distributed systems, as well as calls for new kinds of software and software policy verification that are both broadly available and can offer stronger guarantees on the correctness and safety of these systems. 

The deployment of autonomous AI systems across safety-critical cloud
architectures, financial protocols, distributed enterprise workflows etc. as well as the use of autonomous AI agents for vulnerability scanning and exploitation has exposed fundamental limits in conventional validation of distributed system code and policies. Standard testing methods such as unit testing or fuzzing or manual peer review fail to guarantee correctness across all possible inputs that an AI could use, and also fail to keep up with the rapid rate of code production by AI agents. This divergence introduces security-critical vulnerabilities, including authorization bypasses, privilege escalation, and unintended execution pathways. Enforcing boundaries between distributed systems and verifying the correctness of policies that define those boundaries as well as verifying the behavior of AI agents that interpret, author, and refactor these policies, has never been more critical for the software world. 

Modern distributed systems infrastructure increasingly decouples governance rules and policies from underlying application code into domain-specific policy languages such as AWS's Cedar and Dogwood languages.Policies that control security, authorization, and admission-control systems represent the operational domains that are simultaneously the most
high-consequence to compromise and the most vulnerable to deliberate attacks and unintentional vulnerabilities by coding agents.

Dogwood temporal policies are used in places like Amazon Bedrock AgentCore
Both incorrect policies and the incorrect implementation of agents in code using frameworks like Strands SDK can lead to compromises. Without the correct architectural guardrails and workflows, agents can autonomously improvise and find vulnerabilites and work around incorrectly written policies.  As agents become part of mission-critical distributed systems and as more software is being written by agents, the same tools humans use for verifying policies and software must be made available to agents themselves to allow them to autonomosly test and repair and give feedback on the policies and code they write in response to natural language instructions from humans. 

(Add Amazon AR checking of Dogwwod here and its limitations)

Formal verification provides a mathematically grounded proof that a software policy or workflow strictly satisfies a formal specification across *all* possible inputs, not only a single or subset of inputs as with traditional testing and runtime verification. However, traditional formal methods have historically suffered from prohibitive engineering overhead: authoring formal specifications required scarce technical expertise. The emerging paradigm of *agentic formal verification* resolves this bottleneck by connecting generative foundation models with automated formal tools such as model checkers, which allow agent-driven autonomous closed loops for formal verification, from natural language human prompts. In such frameworks, generative models propose code, specifications, and intermediate proof steps, while deterministic verification backends mechanically validate candidate outputs, providing structured diagnostic signals and counterexamples, that can guide autonomous iterative investigation and repair.

Agentic formal verification provides one answer to the velocity of AI-driven autonomous compromises, AI-agents becoming part of mission-critical distributed systems and AI-agent developed code being used to implement the components and security policies that govern these systems. Agents can autonomously write core specification modules and property modules that model both the logic and the intent of policies and then use model checkers to check if these properties are satisfied and produce counter-examples showing where they fail to hold. However such systems have numerous failings and require a careful design and gating to produce useful, valid results.

An agentic formal verification system built using an agentic framework like Strands SDK that supports complex workflow logic is a possible solution to the problem of agentic formal verification of policy languages like Dogwood.


## What it does
Anchor is a agentic formal verification framework that uses the [TLA+](https://lamport.azurewebsites.net/tla/tla.html) formal specification language and model checker to formally verify Amazon Dogwood temporal policies and Strands SDK agent graph workflows, and provides a Strands agent that allows humans to perform formal verification of these policies and code using natural language questions and prompts without knowing the technical details of the framework or tools.

Anchor allows developers and engineers and administrators to use the benefits of formal verification without requiring the specialized knowledge and skills formal methods typically demands.

Anchor provides:

* [Translators](https://github.com/allisterb/Anchor/tree/master/src/translator) from the Dogwood policy language to TLA+.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/policy/TemporalPolicy) that models a large subset of Dogwood temporal policy semantics, validated in [CI](https://github.com/allisterb/Anchor/actions) against the Dogwood unit test and examples corpus.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/strands) and [Python annotations](https://github.com/allisterb/Anchor/tree/master/src/annotations) that allow Strands SDK users to model multi-agent Strands graph workflows 
* A [model property checker](https://github.com/allisterb/Anchor/tree/master/src/checker) that checks:
     * *derivable* property checks, which can be mechanically derived from all policies e.g. "is this policy vacuous or redundant?"
     * *intentional* property checks where a human or agent authors a check to explicitly capture the intent of a policy or workflow e.g. "Does this firewall policy intentionally block all inbound connections from external addresses?"
* An [MCP server](https://github.com/allisterb/Anchor/tree/master/src/Anchor.MCPServer) that exposes the translator and model property checker as well as knowledge resources that an agent can use to verify Dogwood policies
* A [CLI](https://github.com/allisterb/Anchor/tree/master/src/Anchor.CLI) that provides command-line access to the framework tools and MCP server launcher and can also run the Strands agent autonomously against a natural language questions file.
* A Strands [agentic workflow](https://github.com/allisterb/Anchor/tree/master/src/agent) for autonomous or HITL formal verification of Dogwood policies.


### Advantages of Agentic Formal Verification
Integrating autonomous agents into formal verification infrastructure fundamentally alters the economics and operational guarantees of high-assurance software systems.
#### Eliminating the Proof Engineering Bottleneck 
Historically, the cost of constructing formal proofs exceeded the cost of authoring implementation code by one to two orders of magnitude. Agentic pipelines allow formal verification to scale to general software modules without demanding dedicated formal methods teams.

#### Deterministic Truth Signals Versus Generative Judge Models
Evaluating generative AI with secondary judge models still suffers from issues like the persistence of probabilistic blind spots, sycophancy, and shared hallucinations. Formal verification acts as a non-negotiable filter: candidate code generated by an agent cannot be merged or deployed unless it satisfies the underlying mechanical verifier.

#### Continuous Refactoring and Regression Prevention
In enterprise policy engineering and DevOps workflows, policy changes routinely introduce regressions that remain undetected by standard test suites. Agentic formal verification enables automated continuous verification in CI/CD pipelines. When an AI refactors an existing
permission set or admission rule, the formal engine mathematically tests equivalence against the legacy policy across the entire domain. This allows safe, automated refactoring of mission-critical authorization systems at scale.

## How it works

Anchor's agentic formal verification can proceed in two modes:

* `auto` The agent makes a best-effort attempt to complete formal verification of Dogwood autonomously
* `hitl` Mechanically formalizes as much as possible but drops into HITL mode for difficult workflow steps that need human feedback and guidance

The advantage of `auto` mode is that human doesn't need to intervene but the quality of the results obtained vary significantly. Agentic formal verification is an active [research program](https://arxiv.org/html/2511.17330v1). Despite significant advances, deploying autonomous agents within formal verification loops
introduces subtle failure modes. Because generative models optimize for task completion, they frequently discover pathological shortcuts that satisfy the mechanical verifier while undermining system security.

### Critical Pathologies, Risks, and Failure Modes

#### The Vacuity Trap and Adversarial Specification Gaming
The most prevalent pathology in agentic formal verification is vacuous verification. When an agent is tasked with synthesizing both an implementation and its formal specification, it frequently discovers that the simplest path to satisfying the verifier is to generate trivial or unsatisfiable contracts. Similarly, in auto-active repair systems, when an agent encounters an intractable verification
error, it often exhibits adversarial assertion pruning, modifying the source code or weakening the verification conditions until the verifier passes, effectively discarding the target security property.

Mitigating vacuous verification requires strict syntactic checks and adversarial filtering. One way to implement this is via Strads 


#### The User-Intent Formalization Gap and Semantic Drift
Formal verification only proves that an artifact conforms to a given mathematical specification; it does not prove that the specification accurately reflects the user's implicit real-world intent.
When an agent translates informal natural language requirements into formal specifications, semantic subtleties are frequently lost6. For instance, an agent formalizing an access control policy may properly enforce that only users in an approvers group can approve purchase
orders, but omit an implicit temporal constraint dictating that an individual cannot approve their own purchase requisition. The resulting policy verifies completely against the generated
assertions, yet contains an exploitable business-logic vulnerability.
Automated metrics that evaluate specification quality—such as mutation analysis, symbolic property testing, and reconstruction consistency—are critical to determining whether formal specifications faithfully mirror informal requirements.

Solver Instability, Butterfly Effects, and State Explosion
SMT solvers rely on sophisticated heuristic combinations of DPLL(
), simplex algorithms,
congruence closure, and quantifier instantiation mechanisms such as
-matching5. These
heuristics make solvers non-monotonic and sensitive to minor perturbations, producing solver
butterfly instability12.
Quantifier explosion occurs when an agent synthesizes complex assertions containing nested
universal (
) and existential (
) quantifiers, triggering matching loops in SMT solvers5. The
solver attempts to instantiate infinite chains of uninterpreted terms, causing processes to hang
or exhaust memory19. Syntactic drift introduces a related failure mode: in an automated repair
loop, an agent modifying an unrelated comment, variable name, or irrelevant invariant can
inadvertently alter the internal variable ordering in the solver's heuristic search tree12. A proof
obligation that previously verified in 200 milliseconds may suddenly time out, stalling the entire
autonomous repair pipeline12.
Furthermore, Bounded Model Checking (BMC) guarantees correctness only up to a fixed
execution depth
19. If an autonomous agent relies solely on BMC to certify a loop or recursive
policy rule, vulnerabilities lying at depth
remain invisible, providing an incomplete
guarantee of mathematical assurance5.


The Dogwood temporal policy formal verification makes use of two main external toolsets:
* The TLA+ language [tools](https://github.com/tlaplus/tlaplus)
* The Dogwood language [tools](https://github.com/dogwood-policy/dogwood)

The first step in Anchor formal verification is to mechanically [translate](https://github.com/allisterb/Anchor/blob/master/src/translator/dw_to_tla.py) a Dogwood policy to a TLA+ spec using the Anchor Dogwood policy parser and semantics specs. With a TLA+ specification module that models the policy, the next step is for the agent to write a property module. A property module extends the core policy specification module and defines the logic you want the TLC model checker to verify.

### Strands SDK graph 
## How we built it
Anchor is written in C# and Python. 
| Project |Language| Responsibility |
|---|---|---|
| `Anchor.Runtime` | C#|Shared base types, logging. |
| `Anchor.CLI` | C#| CLI access to the framework tools and the MCP server launcher |
| `Anchor.Verifiers.TLAPlus` | C#| Hosts the TLA+ language tools |
| `Anchor.MCPServer` |C#| MCP server implementation providing agents access to the framework tools and verifiers and knowledge resources including tools for writing TLA+ specs|
| `translator` |Python| Translate Dogwood policies to TLA+ specifications.|
| `check` | Python|Uses the TLC bounded model property checker for verifyng derived and intentional properties|
| `annotations` |Python| Provides annotations to assist in creating TLA+ specs from Strands SDK graph builder workdlows|
| `agent` | Python | Strands SDK agent orchestrator for HITL and autonomous formal verification|