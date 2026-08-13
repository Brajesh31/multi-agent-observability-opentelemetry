"""Document search tool — queries the internal knowledge base.

Simulates a vector or keyword search over enterprise documents.
In a production deployment this would call a search service, vector
database, or internal API.

Every tool invocation is wrapped in an OTel span that captures the
query, result count, and execution time.
"""

from __future__ import annotations

import time

from agent.tracing import error_count, tool_calls, tracer


def search_documents(query: str) -> list[dict]:
    """Search the knowledge base for documents matching the query.

    Args:
        query: The user's search query.

    Returns:
        A list of document metadata dicts with id, title, snippet, and source.
    """
    with tracer.start_as_current_span("tool.search") as span:
        span.set_attribute("tool.name", "search")
        span.set_attribute("tool.query", query[:500])
        span.add_event("tool.input", {"query": query[:2000]})

        try:
            start = time.monotonic()

            # In production: call search API or vector database.
            results = _search_index(query)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("tool.result_count", len(results))
            span.set_attribute("tool.duration_ms", duration_ms)
            span.add_event("tool.output", {"results": str(results)[:2000]})

            tool_calls.add(1, {"tool": "search", "status": "ok"})
            return results

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.status.StatusCode.ERROR)
            error_count.add(1, {"error_type": type(exc).__name__})
            tool_calls.add(1, {"tool": "search", "status": "error"})
            raise


def _search_index(query: str) -> list[dict]:
    """Mock search index returning realistic enterprise document results."""
    query_lower = query.lower()
    results = [
        {
            "id": "doc-001",
            "title": "Q3 2025 Financial Results",
            "snippet": "Revenue grew 18% year-over-year to $124.7M driven by enterprise segment expansion...",
            "source": "internal/finance",
        },
        {
            "id": "doc-002",
            "title": "Annual Operating Review — FY2025",
            "snippet": "Customer acquisition costs decreased 12% while lifetime value increased 8%...",
            "source": "internal/operations",
        },
        {
            "id": "doc-003",
            "title": "Sales Playbook: Enterprise Growth Strategy",
            "snippet": "Key accounts in the healthcare vertical showed 34% quarter-over-quarter growth...",
            "source": "internal/sales",
        },
    ]

    if "revenue" in query_lower or "sales" in query_lower or "growth" in query_lower:
        return results[:1]
    if "report" in query_lower or "review" in query_lower:
        return results[1:2]
    return results
