"""Analysis agent — queries structured data and computes metrics.

This agent is a LangGraph subgraph with two sequential nodes:
1. query_db: Runs a SQL-like query against the internal database.
2. calculate: Computes metrics (growth rates, aggregates) from query results.

The subgraph pattern mirrors the research agent structure, showing
the reusable subgraph architecture common in enterprise deployments.
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, StateGraph

from agent.state import AgentState
from agent.tools.database import query_database
from agent.tools.calculator import calculate
from agent.tracing import node_duration, tracer


def _query_db_node(state: AgentState) -> dict[str, Any]:
    """Query the internal database for structured data.

    Converts the user query into a database query and stores the
    raw results. The query and row count are recorded as span
    attributes for observability.
    """
    with tracer.start_as_current_span("node.query_db") as span:
        span.set_attribute("node.name", "query_db")
        span.set_attribute("agent.query", state.get("query", ""))

        start = time.monotonic()
        results = query_database(state.get("query", ""))
        duration_ms = (time.monotonic() - start) * 1000

        span.set_attribute("agent.row_count", len(results))
        node_duration.record(duration_ms, {"node": "query_db"})

        return {"query_results": results}


def _calculate_node(state: AgentState) -> dict[str, Any]:
    """Compute metrics from the raw query results.

    Performs calculations (e.g., growth rates, percentages) on the
    database results and stores the computed analysis. Each input
    and output is traced for auditability.
    """
    with tracer.start_as_current_span("node.calculate") as span:
        span.set_attribute("node.name", "calculate")
        span.set_attribute(
            "agent.input_rows", len(state.get("query_results", []))
        )

        start = time.monotonic()
        result = calculate(state.get("query_results", []))
        duration_ms = (time.monotonic() - start) * 1000

        span.set_attribute("agent.metrics_computed", str(len(result)))
        node_duration.record(duration_ms, {"node": "calculate"})

        return {"analysis": result}


def build_analysis_subgraph() -> StateGraph:
    """Build and return the analysis subgraph.

    Sequential nodes: query_db → calculate.
    The compiled subgraph is added as a single node in the parent graph.
    """
    builder = StateGraph(AgentState)
    builder.add_node("query_db", _query_db_node)
    builder.add_node("calculate", _calculate_node)
    builder.set_entry_point("query_db")
    builder.add_edge("query_db", "calculate")
    builder.add_edge("calculate", END)
    return builder.compile()
