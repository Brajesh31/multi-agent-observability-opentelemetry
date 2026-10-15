<div align="center">

# Multi-Agent Observability with OpenTelemetry

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)]()
[![OpenTelemetry 1.30](https://img.shields.io/badge/OpenTelemetry-1.30-purple?style=flat-square)]()
[![LangGraph 0.4+](https://img.shields.io/badge/LangGraph-0.4%2B-green?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)]()
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=flat-square)]()

**Production-grade reference implementation demonstrating OpenTelemetry instrumentation patterns in a LangGraph multi-agent system.**

</div>

---

## The Problem — Enterprise Multi-Agent Observability

Multi-agent LLM systems are fundamentally different from traditional distributed services. Each invocation is **non-deterministic**: the supervisor makes routing decisions based on LLM outputs that vary by model, prompt, temperature, and even timestamp. When a query fails — or worse, produces a subtly wrong answer — you cannot simply "replay" it. You need observability.

Below is a catalog of the observability challenges that enterprise multi-agent systems face, organized by concern area. Each problem is addressed in this reference implementation through specific OpenTelemetry patterns (spans, span events, attributes, metrics, baggage, and sampling).

### Agent Routing & Decision Tracking

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **Non-deterministic routing** | The supervisor chose "analysis" instead of "research" for a query. Was that correct? Without recording the LLM response and rationale, you can never know. | Span events with full decision payload (`agent.decision` with `action` and `rationale`) |
| **Infinite agent loops** | The supervisor routes "analysis" → "analysis" → "analysis" repeatedly until timeout. Without hop-count tracking and loop detection, the pipeline runs silently forever. | Span attributes tracking routing history; conditional edges with guardrails |
| **Routing distribution skew** | Over time, 90% of traffic routes to one agent. Is the supervisor biased, or is the workload genuinely skewed? Without aggregate routing counters, you can't distinguish. | Custom metric counters per routing decision (`agent.routing.decision`) |
| **Decision audit trail** | Compliance asks: "On Tuesday at 3pm, why did the system run the database query?" Without immutable decision records, you have no defensible answer. | Span events create an append-only audit log of every routing decision with full context |

### Performance & Cost Attribution

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **Per-agent latency** | LangGraph merges all subgraph execution into a single wall-clock duration. You cannot tell whether research (documents) or analysis (database) was the bottleneck. | Individual span per agent node (`node.research`, `node.analysis`) with duration attributes |
| **Per-tool latency** | A tool call (e.g., database query) might take 2s, but the agent node's span hides this in the total. You need sub-span granularity. | Child spans per tool invocation (`tool.query_db`, `tool.calculate`) nested under the agent span |
| **LLM token cost attribution** | The monthly API bill arrives. Which agent consumed the most tokens? Without per-call token counters tagged by agent and model, costs are unmeasurable. | Counter metric (`agent.llm.tokens`) with attributes `model` and `direction` (input/output) |
| **Context window budgeting** | Each agent appends messages to the shared context. Which agent consumes the most context budget? Without cumulative token tracking, you blow past context limits silently. | Span attributes reporting cumulative input tokens per node |
| **Model-level cost breakdown** | Some agents use an expensive model, others use a cheaper model. Without model-tagged cost metrics, you cannot optimize model selection by agent role. | Metric attributes tagged with `model` per LLM call |

### Error Detection & Root Cause Analysis

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **Error attribution across agent boundaries** | A database tool throws an exception. Was the error caught downstream or did it silently corrupt the answer? Without span error status propagation, the root cause is invisible. | Span status codes and error events propagated to parent spans |
| **Silent data corruption** | The research agent stores malformed documents. The analysis agent silently uses them. The answer is wrong but no exception is thrown. | Span attributes tracking data shape (row count, content length) at every state mutation |
| **LLM hallucination vs tool error** | The final answer is incorrect. Is it an LLM hallucination or a tool returning bad data? Without input/output events on every span, you can't distinguish. | Dual span events per tool call (`tool.input` with raw parameters, `tool.output` with raw result) for replay |
| **Transient failure cascades** | A database timeout cascades into an empty analysis which cascades into a hallucinated answer. Without distributed trace context, each failure looks isolated. | Trace context propagation across all spans using OTel context propagation |

### State & Data Flow

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **State mutation tracking** | Multiple agents read and write the same shared state dict. Which agent corrupted the state? Without state diff tracking, you debug blind. | Span attributes recording key state fields at entry and exit of each node |
| **Data freshness & staleness** | The database tool returns cached data from last week. The analysis agent computes growth rates on stale numbers. | Span attributes with data timestamp and staleness markers |
| **Cross-agent data lineage** | The final answer uses a specific revenue number. Which tool produced it? Which agent processed it? Without attribute propagation, lineage is lost. | Baggage propagation to carry business context across agent boundaries |
| **Parallel execution correctness** | If agents run in parallel, shared state mutations race. Without trace context for fork/join semantics, debugging concurrent state is impossible. | Trace context propagation for concurrent subgraph execution |

### Security & Compliance

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **PII leakage through span data** | A span event captures the user's query which contains PII. This gets exported to the observability backend in plain text. | Attribute redaction and sanitization before recording span events |
| **Access control for traces** | The observability backend contains sensitive business data (revenue numbers, customer PII). Without span-level access controls, compliance is violated. | Span attribute-based access control (ABAC) policies on the backend |
| **Prompt injection detection** | An attacker injects a prompt that exfiltrates data through span output events. | Span event content inspection and alerting on suspicious patterns |

### Business-Critical Production Concerns

| Problem | What breaks without it | OTel Pattern |
|---|---|---|
| **SLA monitoring** | The business commits to 5-second response times for customer queries. Without p50/p95/p99 latency histograms per agent path, you cannot measure SLAs. | Histogram metric (`agent.node.duration`) with agent and path attributes |
| **Cost per-query / per-business-unit** | Finance needs chargeback data. "Which business unit consumed the most LLM tokens?" Without trace-to-metric correlation, chargebacks are guesswork. | Metric counters tagged with business-unit attributes from baggage |
| **Sampling high-volume systems** | At 10k queries/min, exporting every span is prohibitively expensive. Without a sampling strategy, observability costs exceed infrastructure costs. | Head-based sampling with priority sampling decisions per trace |
| **Human-in-the-loop delays** | Enterprise approvals add minutes or hours to agent execution. Without span pause/resume handling, SLAs are miscalculated. | Span duration with explicit pause/resume markers for human review windows |
| **Multi-model observability** | Different agents use different providers (one vendor, another, self-hosted). Without normalized telemetry across all models, you maintain separate dashboards. | Vendor-agnostic span attributes normalized to OTel semantic conventions |
| **Prompt drift & version tracking** | The system prompt changes during a deployment. Old and new prompts produce different routing behavior. Without prompt version in span attributes, behavior shifts are unexplainable. | Span attributes recording prompt version hash per routing decision |

---

## How This Project Solves It

A reference implementation of a LangGraph multi-agent system where every node, tool call, and LLM invocation is instrumented with OpenTelemetry spans, span events, attributes, and metrics — demonstrating the exact patterns cataloged above.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

PRs welcome. Keep contributions focused on improving the instrumentation patterns or adding new observability problems to the catalog.

Last updated: 2026-10-15 18:55 UTC
