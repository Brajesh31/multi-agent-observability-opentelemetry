"""LLM client wrapper with OpenTelemetry instrumentation.

This is the single integration point for language model calls across
all agents. Every LLM invocation — whether for routing, generation,
or synthesis — flows through this module so that tracing, token
accounting, and error handling are consistent.

To swap providers, replace the HTTP client below while keeping the
tracing and metric recording intact.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from agent.config import settings
from agent.tracing import error_count, llm_tokens, tracer


def call_llm(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> str:
    """Send a chat completion request and return the response content.

    Every call is wrapped in an OTel span that records:
    - model name and token counts (attributes, for querying)
    - messages and response text (events, for detailed inspection)
    - duration, error status, and token metrics

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        model: Model identifier. Falls back to config.llm_model.

    Returns:
        The response content string.

    Raises:
        RuntimeError: If LLM_API_KEY is set but the API call fails.
    """
    model = model or settings.llm_model

    with tracer.start_as_current_span("llm.call") as span:
        span.set_attribute("llm.model", model)

        input_tokens = _estimate_tokens(messages)
        span.set_attribute("llm.input_tokens", input_tokens)
        span.add_event("llm.messages", {"content": str(messages)[:2000]})

        start = time.monotonic()

        if settings.llm_api_key:
            response = _call_remote(messages, model)
        else:
            response = _mock_response(messages)

        duration_ms = (time.monotonic() - start) * 1000

        output_tokens = _estimate_tokens(response)
        span.set_attribute("llm.output_tokens", output_tokens)
        span.set_attribute("llm.duration_ms", duration_ms)
        span.add_event("llm.response", {"content": str(response)[:2000]})

        llm_tokens.add(input_tokens, {"model": model, "direction": "input"})
        llm_tokens.add(output_tokens, {"model": model, "direction": "output"})

        return response


def _call_remote(messages: list[dict[str, str]], model: str) -> str:
    """Make an HTTP request to an LLM provider's chat completion endpoint.

    Uses urllib.request (stdlib) so there is no vendor SDK dependency.
    Swap this function for a different provider's SDK as needed.
    """
    import urllib.request

    body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        settings.llm_api_base,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        error_count.add(1, {"error_type": type(exc).__name__})
        raise


def _mock_response(messages: list[dict[str, str]]) -> str:
    """Return a plausible structured response when no API key is configured.

    Designed for local development and CI. The response content is
    derived from the messages so the agent graph can execute end-to-end.
    """
    combined = " ".join(
        m.get("content", "") for m in messages if m.get("content")
    ).lower()

    if "route" in combined or "next_agent" in combined:
        if "analysis complete: true" in combined:
            return json.dumps({
                "next_agent": "respond",
                "rationale": "All data collected, synthesizing final answer",
            })
        if any(kw in combined for kw in ("revenue", "sales", "growth", "quarter")):
            return json.dumps({
                "next_agent": "analysis",
                "rationale": "Query requires structured data analysis",
            })
        if any(kw in combined for kw in ("document", "report", "policy", "read")):
            return json.dumps({
                "next_agent": "research",
                "rationale": "Query requires document retrieval",
            })
        return json.dumps({
            "next_agent": "research",
            "rationale": "Researching before analysis",
        })

    if "synthesize" in combined or "summarize" in combined:
        return (
            "Based on the retrieved documents and database analysis, "
            "the key findings show consistent growth across Q3 with "
            "primary drivers being new customer acquisition and "
            "expansion within existing accounts."
        )

    return "I understand the request and will process it accordingly."


def _estimate_tokens(text: str | list[dict[str, str]]) -> int:
    """Rough token estimate: 1 token ~4 characters for English text.

    Used for span attributes and metric recording. Production systems
    should replace this with the provider's actual token count API.
    """
    if isinstance(text, list):
        text = str(text)
    return len(text) // 4
