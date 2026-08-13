"""Database query tool — executes SQL queries against internal analytics DB.

Simulates querying a structured data store (OLAP, data warehouse, or
metrics API). In production this would connect to Snowflake, BigQuery,
PostgreSQL, or an internal metrics service.

The span captures the SQL query, row count, and execution time.
"""

from __future__ import annotations

import time

from opentelemetry import trace

from agent.tracing import error_count, tool_calls, tracer


QUERY_TEMPLATES: dict[str, str] = {
    "revenue": "SELECT quarter, revenue, growth_pct FROM revenue WHERE quarter = 'Q3-2025'",
    "sales": "SELECT segment, revenue, customers FROM sales WHERE quarter = 'Q3-2025'",
    "growth": "SELECT quarter, revenue, growth_pct, drivers FROM growth_metrics WHERE quarter = 'Q3-2025'",
}


def query_database(query: str) -> list[dict]:
    """Execute a SQL query against the analytics database.

    Args:
        query: The user query string used to select an appropriate query.

    Returns:
        A list of row dicts with column names as keys.
    """
    with tracer.start_as_current_span("tool.query_db") as span:
        span.set_attribute("tool.name", "query_db")

        sql = _build_sql(query)
        span.set_attribute("tool.sql", sql[:500])

        try:
            start = time.monotonic()

            rows = _execute(sql)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("tool.row_count", len(rows))
            span.set_attribute("tool.duration_ms", duration_ms)
            span.add_event("tool.output", {"rows": str(rows)[:2000]})

            tool_calls.add(1, {"tool": "query_db", "status": "ok"})
            return rows

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.status.StatusCode.ERROR)
            error_count.add(1, {"error_type": type(exc).__name__})
            tool_calls.add(1, {"tool": "query_db", "status": "error"})
            raise


def _build_sql(user_query: str) -> str:
    """Map a user query to a SQL template.

    In production this would use an NL2SQL model or a fixed set of
    parameterized queries. For this reference, keyword matching is used.
    """
    q = user_query.lower()
    for keyword, sql in QUERY_TEMPLATES.items():
        if keyword in q:
            return sql
    return QUERY_TEMPLATES["revenue"]


def _execute(sql: str) -> list[dict]:
    """Mock database returning realistic financial data rows."""
    return [
        {
            "quarter": "Q3-2025",
            "revenue": 124700000,
            "growth_pct": 18.0,
            "segment": "enterprise",
            "customers": 847,
            "drivers": "Healthcare vertical expansion, APAC growth",
        },
        {
            "quarter": "Q3-2025",
            "revenue": 46500000,
            "growth_pct": 9.0,
            "segment": "smb",
            "customers": 2134,
            "drivers": "Self-service adoption, improved onboarding",
        },
    ]
