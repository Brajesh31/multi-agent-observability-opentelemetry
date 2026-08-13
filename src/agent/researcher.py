"""Research agent — retrieves and reads internal documents.

This agent is a LangGraph subgraph with two sequential nodes:
1. retrieve: Searches the knowledge base for documents matching the query.
2. read: Fetches the full content of the top result.

The subgraph pattern encapsulates agent logic so that it can be
developed, tested, and traced independently of the parent graph.
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, StateGraph

from agent.state import AgentState
from agent.tools.search import search_documents
from agent.tools.reader import read_document
from agent.tracing import node_duration, tracer


def _retrieve_node(state: AgentState) -> dict[str, Any]:
    """Search the knowledge base for documents matching the user query.

    The search tool returns a list of document metadata (title, snippet,
    source). The raw results are stored in state.documents for the next
    node to consume.
    """
    with tracer.start_as_current_span("node.retrieve") as span:
        span.set_attribute("node.name", "retrieve")
        span.set_attribute("agent.query", state.get("query", ""))

        start = time.monotonic()
        results = search_documents(state.get("query", ""))
        duration_ms = (time.monotonic() - start) * 1000

        span.set_attribute("agent.result_count", len(results))
        node_duration.record(duration_ms, {"node": "retrieve"})

        return {"documents": results}


def _read_node(state: AgentState) -> dict[str, Any]:
    """Read the full content of the top document returned by retrieve.

    Enriches the first document entry with full body text. If no
    documents were found, this node is a no-op.
    """
    with tracer.start_as_current_span("node.read") as span:
        span.set_attribute("node.name", "read")

        documents = state.get("documents", [])
        if not documents:
            span.set_attribute("agent.skipped", "no documents to read")
            return {}

        start = time.monotonic()
        content = read_document(documents[0].get("id", ""))
        duration_ms = (time.monotonic() - start) * 1000

        documents[0]["content"] = content
        span.set_attribute("agent.document_id", documents[0].get("id", ""))
        span.set_attribute("agent.content_length", len(content))
        node_duration.record(duration_ms, {"node": "read"})

        return {"documents": documents}


def build_research_subgraph() -> StateGraph:
    """Build and return the research subgraph.

    The subgraph has two sequential nodes: retrieve → read.
    It reads from and writes to AgentState like any other node.
    """
    builder = StateGraph(AgentState)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("read", _read_node)
    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "read")
    builder.add_edge("read", END)
    return builder.compile()
