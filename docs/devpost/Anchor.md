# Anchor: An agentic formal verification framework for Amazon Dogwood policies and Strands SDK graph workflows

## Inspiration
The recent explosion of autonomous AI-driven security compromises and AI model sandbox escapes, compounded by the growing prevalence of AI-generated code, has led to a huge amount of anxiety amoung developers and maintainers of cloud-based distributed systems, as well as calls for new kinds of software and software policy verification that are both broadly available and can offer stronger guarantees on the correctness and safety of these systems. 

The deployment of autonomous AI systems across safety-critical cloud
architectures, financial protocols, distributed enterprise workflows etc. as well as the use of autonomous AI agents for vulnerability scanning and exploitation has exposed fundamental limits in conventional validation of distributed system code and policies. Standard testing methods such as unit testing or fuzzing or manual peer review fail to guarantee correctness across all possible inputs that an AI could use, and also fail to keep up with the rapid rate of code production by AI agents. This divergence introduces security-critical vulnerabilities, including authorization bypasses, privilege escalation, and unintended execution pathways. Enforcing boundaries between distributed systems and verifying the correctness of policies that define those boundaries as well as verifying the behavior of AI agents that interpret, author, and refactor these policies, has never been more critical for the software world. 

Both incorrect policies and the incorrect implementation of agents in code using frameworks like Strands SDK can lead to compromises. Without the correct architectural guardrails and workflows, agents can autonomously improvise and find vulnerabilites and work around incorrectly written policies.  As agents become part of mission-critical distributed systems and as more software is being written by agents, the same tools humans use for verifying policies and software must be made available to agents themselves to allow them to autonomosly test and repair and give feedback on the policies and code they write in response to natural language instructions from humans. 

Formal verification provides a mathematically grounded proof that a software policy or workflow strictly satisfies a formal specification across *all* possible inputs, not only a single or subset of inputs as with traditional testing and runtime verification. However, traditional formal methods have historically suffered from prohibitive engineering overhead: authoring formal specifications required scarce technical expertise. The emerging paradigm of *agentic formal verification* resolves this bottleneck by connecting generative foundation models with automated formal tools such as model checkers, which allow agent-driven autonomous closed loops for formal verification, from natural language human prompts. In such frameworks, generative models propose code, specifications, and intermediate proof steps, while deterministic verification backends mechanically validate candidate outputs, providing structured diagnostic signals and counterexamples, that can guide autonomous iterative investigation and repair.


(Talk about Amazon Dogwood policy and automated reasoning)

Agentic formal verification provides one answer to the velocity of AI-driven autonomous compromises, AI-agents becoming part of mission-critical distributed systems and AI-agent developed code being used to implement the components and security policies that govern these systems.


## What it does
Anchor is a agentic formal verification framework that uses the [TLA+](https://lamport.azurewebsites.net/tla/tla.html) formal specification language and model checker to formally verify Amazon Dogwood temporal policies and Strands SDK agent graph workflows, and provides a Strands agent that allows humans to perform formal verification of these policies and code using natural language questions and prompts without knowing the technical details of the framework.


Anchor provides:

* [Translators](https://github.com/allisterb/Anchor/tree/master/src/translator) from the Dogwood policy language and Strands workflow graphs to TLA+.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/policy/TemporalPolicy) that models a large subset of Dogwood temporal policy semantics, validated in [CI](https://github.com/allisterb/Anchor/actions) against the Dogwood unit test and examples corpus.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/strands) and [Python annotations](https://github.com/allisterb/Anchor/tree/master/src/annotations) that allow Strands SDK users to model multi-agent Strands graph workflows 
* A [model property checker](https://github.com/allisterb/Anchor/tree/master/src/checker) that checks:
     * *derivable* property checks, which can be mechanically derived from all policies e.g. "is this policy vacuous or redundant?"
     * *intentional* property checks where a human or agent authors a check to explicitly capture the intent of a policy or workflow e.g. "Does this firewall policy intentionally block all inbound connections from external addresses?"
* An [MCP server](https://github.com/allisterb/Anchor/tree/master/src/Anchor.MCPServer) that exposes the translator and model property checker as well as knowledge resources that an agent can use to verify Dogwood policies
* A [CLI](https://github.com/allisterb/Anchor/tree/master/src/Anchor.CLI) that provides command-line access to the framework tools and MCP server launcher and can also run the Strands agent autonomously against a natural language questions file.

## How it works

### Dogwood temporal policy formal verification
Anchor's Dogwood formal verification makes use of two main external toolsets:
* The TLA+ language [tools](https://github.com/tlaplus/tlaplus)
* The Dogwood language [tools](https://github.com/dogwood-policy/dogwood)


The first step in Anchor formal verification is to translate a Dogwood policy to a TLA+ spec using the Dogwood semantics spec


## How we built it
Anchor is written in C# and Python. 
| Project |Language| Responsibility |
|---|---|---|
| `Anchor.Runtime` | C#|Shared base types, logging. |
| `Anchor.CLI` | C#| CLI access to the framework tools and the MCP server launcher |
| `Anchor.Verifiers.TLAPlus` | C#| Hosts the TLA+ language tools |
| `Anchor.MCPServer` |C#| MCP server implementation providing agents access to the framework tools and verifiers and knowledge resources including tools for writing TLA+ specs|
| `translator` |Python| Translate Dogwood policies to TLA+ specifications.|
| `check` | Python|TLC model property checker for verifyng derived and intentional properties|
| `annotations` |Python| Provides annotations to assist in creating TLA+ specs from Strands SDK graph builder workdlows|
| `agent` | Python | Strands SDK agent orchestrator for HITL and autonomous formal verification|