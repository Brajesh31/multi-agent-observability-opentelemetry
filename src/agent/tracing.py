"""OpenTelemetry initialization and shared tracer instance.

This is the only module that imports OpenTelemetry SDK internals.
All other modules import the `tracer` and metric instruments from here
and use them directly via start_as_current_span / add / record.

This follows the standard OTel pattern: one provider per service,
one tracer per service, shared across all components.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

tracer: trace.Tracer | None = None
meter: Meter | None = None

node_duration: Histogram | None = None
tool_calls: Counter | None = None
llm_tokens: Counter | None = None
error_count: Counter | None = None


def setup_telemetry(
    service_name: str = "enterprise-agent",
    otlp_endpoint: str = "",
) -> None:
    """Initialize the OpenTelemetry trace and metric pipelines.

    Call once at application startup before any agent code runs.
    Falls back to console export when no OTLP endpoint is configured,
    which is the standard pattern for local development.

    Args:
        service_name: Identifies this service in traces and metrics.
        otlp_endpoint: gRPC endpoint for OTLP export (e.g., "http://localhost:4317").
            Empty string means console export only.
    """
    global tracer, meter, node_duration, tool_calls, llm_tokens, error_count

    # --- Tracing ---
    trace_provider = TracerProvider()

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        trace_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        trace_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )

    trace.set_tracer_provider(trace_provider)
    tracer = trace_provider.get_tracer(service_name)

    # --- Metrics ---
    metric_reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(),
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    meter = meter_provider.get_meter(service_name)

    node_duration = meter.create_histogram(
        name="agent.node.duration",
        unit="ms",
        description="Execution time per graph node",
    )

    tool_calls = meter.create_counter(
        name="agent.tool.calls",
        unit="{call}",
        description="Tool invocations by name and status",
    )

    llm_tokens = meter.create_counter(
        name="agent.llm.tokens",
        unit="{token}",
        description="LLM token usage by model and direction",
    )

    error_count = meter.create_counter(
        name="agent.errors",
        unit="{error}",
        description="Errors by error type",
    )
