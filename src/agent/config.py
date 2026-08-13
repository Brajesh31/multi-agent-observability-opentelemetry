"""Application configuration via environment variables.

Follows the common pattern of a centralized settings object loaded
from environment variables at startup. All agent components reference
this module for configuration rather than reading env vars directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Immutable configuration loaded once at application startup.

    Attributes prefixed with llm_ control the language model provider.
    Attributes prefixed with otel_ control OpenTelemetry export.
    """

    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("LLM_API_KEY", ""),
    )
    llm_api_base: str = field(
        default_factory=lambda: os.environ.get(
            "LLM_API_BASE", ""
        ),
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get("LLM_MODEL", ""),
    )

    otel_service_name: str = field(
        default_factory=lambda: os.environ.get(
            "OTEL_SERVICE_NAME", "enterprise-agent"
        ),
    )
    otel_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", ""
        ),
    )


settings = Settings()
