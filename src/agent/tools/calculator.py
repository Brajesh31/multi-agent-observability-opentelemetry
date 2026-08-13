"""Calculator tool — computes business metrics from raw data.

Handles common enterprise calculations: growth rates, percentages,
aggregates, and trend analysis.

The span captures every input and output for auditability,
so downstream consumers can verify how a metric was derived.
"""

from __future__ import annotations

import time
from typing import Any

from opentelemetry import trace

from agent.tracing import error_count, tool_calls, tracer


def calculate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute business metrics from database result rows.

    Args:
        rows: Raw database rows from the query tool.

    Returns:
        A dict of computed metrics with human-readable labels.
    """
    with tracer.start_as_current_span("tool.calculate") as span:
        span.set_attribute("tool.name", "calculate")
        span.set_attribute("tool.input_rows", len(rows))
        span.add_event("tool.input", {"rows": str(rows)[:2000]})

        try:
            start = time.monotonic()

            result = _compute_metrics(rows)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("tool.metrics_count", len(result))
            span.set_attribute("tool.duration_ms", duration_ms)
            span.add_event("tool.output", {"result": str(result)[:2000]})

            tool_calls.add(1, {"tool": "calculate", "status": "ok"})
            return result

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.status.StatusCode.ERROR)
            error_count.add(1, {"error_type": type(exc).__name__})
            tool_calls.add(1, {"tool": "calculate", "status": "error"})
            raise


def _compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate metrics from the given rows.

    Demonstrates a realistic calculation pipeline: sum revenues,
    compute weighted averages, and determine growth contributions.
    """
    total_revenue = sum(r.get("revenue", 0) for r in rows)
    total_customers = sum(r.get("customers", 0) for r in rows)
    avg_growth = (
        sum(r.get("growth_pct", 0) for r in rows) / len(rows)
        if rows
        else 0.0
    )

    revenue_per_customer = (
        round(total_revenue / total_customers, 2) if total_customers else 0.0
    )

    return {
        "total_revenue": total_revenue,
        "total_customers": total_customers,
        "average_growth_pct": round(avg_growth, 1),
        "revenue_per_customer": revenue_per_customer,
        "row_count": len(rows),
        "segments": [r.get("segment", "unknown") for r in rows],
    }
