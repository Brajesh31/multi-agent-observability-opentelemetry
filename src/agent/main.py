"""Application entry point — wires configuration, telemetry, and the graph.

Run with:
    LLM_API_KEY=your-key python -m agent
    python -m agent  (uses mock LLM responses)

Expected console output shows the full trace waterfall:
    node.supervisor (42ms)
      agent.query: "What was Q3 revenue growth?"
      agent.routing_decision: research
      ~ agent.decision
    node.retrieve (12ms)
      ...
"""

from __future__ import annotations

import sys

from agent.config import settings
from agent.tracing import setup_telemetry

# Initialize telemetry before any module imports that capture the tracer.
setup_telemetry(
    service_name=settings.otel_service_name,
    otlp_endpoint=settings.otel_endpoint,
)

from agent.pipeline import build_pipeline


def main() -> None:
    """Run the multi-agent system with a sample query.

    Builds the graph and executes the agent pipeline.
    All spans and metrics are exported to the configured destination.
    """
    graph = build_pipeline()

    sample_query = "What was our Q3 revenue growth and what drove it?"

    print(f"\n{'='*60}")
    print(f"Query: {sample_query}")
    print(f"{'='*60}\n")

    result = graph.invoke({
        "query": sample_query,
        "messages": [{"role": "user", "content": sample_query}],
        "documents": [],
        "query_results": [],
        "analysis": {},
        "answer": "",
        "next_agent": "",
        "rationale": "",
        "errors": [],
    })

    print(f"\n{'='*60}")
    print("Final Answer:")
    print(f"{'='*60}")
    print(result.get("answer", "No answer generated."))
    print()

    route_history = []
    if result.get("rationale"):
        route_history.append(result["rationale"])
    if route_history:
        print(f"Routing decisions: {route_history}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
