"""Shared state definition for the multi-agent graph.

This TypedDict is the single source of truth for what flows through
the LangGraph pipeline. Every node reads from and writes to this state.
LangGraph handles merging updates, including message accumulation
via the add_messages reducer.
"""

from __future__ import annotations

from typing import Annotated, Any

from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State propagated through every node in the agent graph.

    Fields:
        query: The original user request.
        messages: Full conversation history accumulated via add_messages reducer.
        documents: Retrieved document chunks from the research agent.
        query_results: Raw rows returned by the database tool.
        analysis: Computed metrics and interpretations (e.g., growth rates).
        answer: Final synthesized response to the user.
        next_agent: Routing target set by the supervisor ("research", "analysis", "respond").
        rationale: The supervisor's reasoning for the most recent routing decision.
        errors: Accumulated error messages across all nodes.
    """

    query: str
    messages: Annotated[list, add_messages]
    documents: list[dict[str, Any]]
    query_results: list[dict[str, Any]]
    analysis: dict[str, Any]
    answer: str
    next_agent: str
    rationale: str
    errors: list[str]
