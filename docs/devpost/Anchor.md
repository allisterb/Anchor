# Anchor: An agentic formal verification framework for Amazon Dogwood policies and Strands SDK graph workflows

## Inspiration
The recent explosion of autonomous AI-driven security compromises and AI model sandbox escapes, compounded by the growing prevalence of AI-generated code, has led both to a huge amount of anxiety amoung developers and maintainers of cloud-based distributed systems, as well as calls for new kinds of software and software policies that can offer stronger guarantees on the correctness and safety of these systems. 

The deployment of autonomous AI systems across safety-critical cloud
architectures, financial protocols, distributed enterprise workflows etc. has exposed fundamental limits in conventional validation of code and policies. Standard testing methods such as unit testing or fuzzing or manual peer review fail to guarantee correctness across all possible inputs that an AI could use and fail to keep up with the rapid rate of code production by AI agents. This divergence introduces security-critical vulnerabilities, including authorization bypasses, privilege escalation, and unintended execution pathways. Enforcing boundaries between distributed systems and verifying the correctness of policies that define those boundaries as well as verifying the behavior of AI agents that interpret, author, and refactor these policies, has never been more critical for the software world. 

Both incorrect policies and the incorrect implementation of agents in code using frameworks like Strands SDK can lead to compromises as without the correct architectural guardrails and workflows agents can autonomously improvise and find vulnerabilites and work around incorrectly written policies.  As more software is being written by agents the same tools humans use for verifying policies and software must be made available to agents themselves to allow them to autonomosly test and repair and give feedback on the policies and code they write in response to natural language instructions from humans. 

Formal verification—is a mathematically grounded proof that a software policy or workflow strictly satisfies a formal specification across all possible inputs. However, traditional formal methods have historically suffered from prohibitive engineering overhead: authoring formal specifications required scarce technical expertise. The emerging paradigm of *agentic formal verification* resolves this bottleneck by coupling
generative foundation models with automated formal tools—such model checkers, which allow agent-driven autonomous closed loops for formal verification. In such frameworks, generative models propose code, specifications, and intermediate proof steps, while deterministic verification backends mechanically validate candidate outputs, providing structured diagnostic signals and counterexamples that guide autonomous iterative repair.


## What it does
Anchor is a agentic formal verification framework that uses the [TLA+](https://lamport.azurewebsites.net/tla/tla.html) language and model checker to formally verify Amazon Dogwood temporal policie and Strands SDK graph workflows, and provides a Strands agent that allows humans to utilize formal verification of these policies and code without knowing the technical details of the framework.


Anchor provides:

* [Translators](https://github.com/allisterb/Anchor/tree/master/src/translator) from the Dogwood policy language and Strands workflow graphs to TLA+.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/policy/TemporalPolicy) that models a large subset of Dogwood temporal policy semantics, validated in [CI](https://github.com/allisterb/Anchor/actions) against the Dogwood unit test and examples corpus.
* A [specification](https://github.com/allisterb/Anchor/tree/master/specs/strands) and [Python annotations](https://github.com/allisterb/Anchor/tree/master/src/annotations) that allow Strands SDK users to model multi-agent Strands graph workflows 
* A model property checker that allows both *derivable* property checks, which can be mechanically derived from all policies or graph code e.g. is this policy vacuous or does this graph have cycles, as well as *intentional* property checks where a human or agents authors a check to explicitly capture the intent of a policy or workflowthat test if 