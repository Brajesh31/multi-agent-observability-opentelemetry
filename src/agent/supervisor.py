"""Supervisor agent — orchestrates the multi-agent workflow.

The supervisor is the central routing node in the graph. It examines
the current state (query, collected data, error history) and decides
which specialist agent should run next: research (document retrieval),
analysis (data querying), or respond (final synthesis).

Each routing decision is recorded as a span with the reasoning
attached, giving full auditability of why the agent chose a path.
"""

from __future__ import annotations

import json
import time

from agent.llm import call_llm
from agent.state import AgentState
from agent.tracing import error_count, node_duration, tracer

_ROUTING_PROMPT = """You are a routing supervisor for a multi-agent system.
Given the user query and the current state, decide which agent should run next.

Available agents:
- research: Retrieves and reads documents from the knowledge base
- analysis: Queries structured data and computes metrics
- respond: Synthesizes all collected data into a final answer

Respond with JSON only: {"next_agent": "<agent_name>", "rationale": "<why>"}
If the user query mentions documents, reports, or policies, route to research.
If it mentions revenue, sales, growth, or metrics, route to analysis.
If all necessary data has been collected, route to respond."""


def supervisor_node(state: AgentState) -> dict:
    """Evaluate the current state and decide the next agent.

    This node runs every cycle before a specialist agent executes.
    It records the routing decision as a span event with the
    full reasoning, creating an auditable decision trail.

    Returns:
        dict with updates to next_agent, rationale, and messages.
    """
    with tracer.start_as_current_span("node.supervisor") as span:
        span.set_attribute("agent.query", state.get("query", ""))
        span.set_attribute("agent.next_agent", state.get("next_agent", ""))
        span.set_attribute(
            "agent.documents_collected", str(len(state.get("documents", [])))
        )
        span.set_attribute(
            "agent.has_analysis", str(state.get("analysis", {}) != {})
        )

        start = time.monotonic()

        messages = [
            {"role": "system", "content": _ROUTING_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Query: {state.get('query', '')}\n"
                    f"Documents collected: {len(state.get('documents', []))}\n"
                    f"Analysis complete: {state.get('analysis', {}) != {}}\n"
                    f"Errors encountered: {state.get('errors', [])}"
                ),
            },
        ]

        response = call_llm(messages)
        duration_ms = (time.monotonic() - start) * 1000
        node_duration.record(duration_ms, {"node": "supervisor"})

        try:
            decision = json.loads(response)
            next_agent = decision.get("next_agent", "research")
            rationale = decision.get("rationale", "")
        except (json.JSONDecodeError, KeyError) as exc:
            error_count.add(1, {"error_type": type(exc).__name__})
            next_agent = "research"
            rationale = "Failed to parse routing decision, defaulting to research"

        span.set_attribute("agent.routing_decision", next_agent)
        span.add_event(
            "agent.decision",
            {
                "action": next_agent,
                "rationale": rationale[:2000],
            },
        )

        return {
            "next_agent": next_agent,
            "rationale": rationale,
            "messages": [
                {"role": "assistant", "content": f"Routing decision: {next_agent}"}
            ],
        }
