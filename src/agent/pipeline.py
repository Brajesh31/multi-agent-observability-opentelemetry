"""Graph pipeline — defines the multi-agent topology.

This module assembles the supervisor, subgraphs, and routing logic
into a single executable LangGraph graph. The structure follows the
common enterprise pattern: a supervisor node routes to specialist
subgraphs, which return control to the supervisor for the next decision.

Topology:
    supervisor (router)
      ├── research subgraph (retrieve → read) → supervisor
      ├── analysis subgraph (query_db → calculate) → supervisor
      └── respond node → END
"""

from __future__ import annotations

import time

from langgraph.graph import END, StateGraph

from agent.analyst import build_analysis_subgraph
from agent.researcher import build_research_subgraph
from agent.state import AgentState
from agent.tracing import node_duration, tracer


def _respond_node(state: AgentState) -> dict:
    """Synthesize all collected data into the final answer.

    This node runs after the supervisor decides that enough data
    has been collected. It calls the LLM one final time with the
    full context and stores the result as the answer.
    """
    with tracer.start_as_current_span("node.respond") as span:
        span.set_attribute("node.name", "respond")
        span.set_attribute(
            "agent.documents_count", len(state.get("documents", []))
        )
        span.set_attribute(
            "agent.has_analysis", str(state.get("analysis", {}) != {})
        )

        from agent.llm import call_llm

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful enterprise assistant. Synthesize the "
                    "retrieved documents and analysis into a clear answer."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Query: {state.get('query', '')}\n\n"
                    f"Documents:\n{state.get('documents', [])}\n\n"
                    f"Analysis:\n{state.get('analysis', {})}"
                ),
            },
        ]

        start = time.monotonic()
        response = call_llm(messages)
        duration_ms = (time.monotonic() - start) * 1000

        span.set_attribute("agent.answer_length", len(response))
        span.add_event("agent.answer", {"content": response[:2000]})
        node_duration.record(duration_ms, {"node": "respond"})

        return {
            "answer": response,
            "next_agent": "__end__",
        }


def _router(state: AgentState) -> str:
    """Conditional edge function that returns the next node name.

    Reads the supervisor's decision from state and routes accordingly.
    Returning "__end__" terminates the graph.
    """
    next_agent = state.get("next_agent", "research")
    if next_agent in ("research", "analysis", "respond"):
        return next_agent
    return "__end__"


def build_pipeline() -> StateGraph:
    """Assemble and compile the full multi-agent graph.

    Returns:
        A compiled LangGraph that can be invoked with an AgentState dict.
    """
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", _supervisor_with_tracing)
    builder.add_node("research", build_research_subgraph())
    builder.add_node("analysis", build_analysis_subgraph())
    builder.add_node("respond", _respond_node)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        _router,
        {
            "research": "research",
            "analysis": "analysis",
            "respond": "respond",
            "__end__": END,
        },
    )

    builder.add_edge("research", "supervisor")
    builder.add_edge("analysis", "supervisor")
    builder.add_edge("respond", END)

    return builder.compile()


def _supervisor_with_tracing(state: AgentState) -> dict:
    """Wrapper around the supervisor that adds graph-level tracing.

    The supervisor node itself is defined in supervisor.py, but the
    routing decision and node timing are captured here at the graph
    level so the trace hierarchy is consistent.
    """
    from agent.supervisor import supervisor_node

    return supervisor_node(state)
