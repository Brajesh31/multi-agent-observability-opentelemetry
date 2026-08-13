"""Document reader tool — fetches full document content.

Retrieves the complete body text for a document given its ID.
In production this would call a document store API, blob storage,
or content management system.

The span captures the document ID, content length, and read duration.
"""

from __future__ import annotations

import time

from opentelemetry import trace

from agent.tracing import error_count, tool_calls, tracer


def read_document(document_id: str) -> str:
    """Fetch the full content of a document.

    Args:
        document_id: The unique identifier of the document to read.

    Returns:
        The full text content of the document.
    """
    with tracer.start_as_current_span("tool.read") as span:
        span.set_attribute("tool.name", "read")
        span.set_attribute("tool.document_id", document_id)

        try:
            start = time.monotonic()

            content = _fetch_document(document_id)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("tool.content_length", len(content))
            span.set_attribute("tool.duration_ms", duration_ms)
            span.add_event("tool.output", {"content": content[:2000]})

            tool_calls.add(1, {"tool": "read", "status": "ok"})
            return content

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.status.StatusCode.ERROR)
            error_count.add(1, {"error_type": type(exc).__name__})
            tool_calls.add(1, {"tool": "read", "status": "error"})
            raise


def _fetch_document(document_id: str) -> str:
    """Mock document store returning realistic enterprise document content."""
    documents = {
        "doc-001": (
            "Q3 2025 Financial Results\n"
            "========================\n"
            "Total Revenue: $124.7M (18% YoY growth)\n"
            "Enterprise Segment: $78.2M (24% YoY growth)\n"
            "SMB Segment: $46.5M (9% YoY growth)\n"
            "Gross Margin: 72.3% (vs 70.1% Q3 2024)\n"
            "New Customers: 847 (12% increase)\n"
            "Customer Churn: 2.1% (improved from 2.8%)\n"
            "\nKey Drivers:\n"
            "- Healthcare vertical grew 34% QoQ\n"
            "- Enterprise expansion revenue up 41%\n"
            "- APAC region showed strongest growth at 28%\n"
        ),
        "doc-002": (
            "Annual Operating Review — FY2025\n"
            "===============================\n"
            "Customer Acquisition Cost (CAC): $4,200 (down 12% YoY)\n"
            "Customer Lifetime Value (LTV): $48,000 (up 8% YoY)\n"
            "LTV/CAC Ratio: 11.4x (target: 10x)\n"
            "Net Revenue Retention: 118%\n"
            "Employee Count: 2,340 (up 15%)\n"
            "R&D Spend: $31.2M (25% of revenue)\n"
        ),
    }
    return documents.get(
        document_id,
        f"No content found for document {document_id}",
    )
