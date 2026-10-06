from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import sys
from time import perf_counter
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Span
from starlette.types import ASGIApp, Message, Receive, Scope, Send


SERVICE_NAME = "multi-tenant-saas-api"
DEFAULT_SERVICE_VERSION = "1.0.0"
REQUEST_LOGGER_NAME = "app.http"


@dataclass(frozen=True)
class TelemetrySettings:
    enabled: bool
    service_name: str
    service_version: str
    environment: str
    protocol: str

    @classmethod
    def from_environment(cls) -> TelemetrySettings:
        raw_enabled = os.getenv("OTEL_ENABLED", "false").strip().lower()
        if raw_enabled not in {"true", "false"}:
            raise ValueError("OTEL_ENABLED must be either true or false")

        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").strip()
        if protocol != "http/protobuf":
            raise ValueError(
                "This service supports OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf"
            )

        return cls(
            enabled=raw_enabled == "true",
            service_name=os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME),
            service_version=os.getenv("APP_VERSION", DEFAULT_SERVICE_VERSION),
            environment=os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
            protocol=protocol,
        )


@dataclass
class TelemetryRuntime:
    settings: TelemetrySettings
    tracer_provider: TracerProvider | None
    meter_provider: MeterProvider | None
    request_counter: Any
    request_duration: Any

    def instrument(self, app: Any) -> None:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
            server_request_hook=sanitize_http_span,
            http_capture_headers_server_request=["x-tenant-id"],
            http_capture_headers_server_response=["content-type"],
            http_capture_headers_sanitize_fields=[
                "x-tenant-id",
                "authorization",
                "proxy-authorization",
                "cookie",
                "set-cookie",
                ".*token.*",
                ".*secret.*",
                ".*password.*",
                ".*key.*",
            ],
        )

    def shutdown(self) -> None:
        if self.meter_provider is not None:
            self.meter_provider.shutdown()
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()


def sanitize_http_span(span: Span, scope: Scope) -> None:
    if not span.is_recording():
        return

    for attribute in ("http.url", "http.target", "url.full", "url.path", "url.query"):
        span.set_attribute(attribute, "/")

    span_context = span.get_span_context()
    scope.setdefault("state", {})["otel_trace_id"] = f"{span_context.trace_id:032x}"
    scope["state"]["otel_span_id"] = f"{span_context.span_id:016x}"


def configure_telemetry(
    settings: TelemetrySettings | None = None,
    *,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
) -> TelemetryRuntime:
    settings = settings or TelemetrySettings.from_environment()
    tracer_provider = None
    meter_provider = None

    if settings.enabled:
        resource = Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
                "deployment.environment.name": settings.environment,
            }
        )
        tracer_provider = TracerProvider(resource=resource)
        if span_exporter is None:
            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter())
            )
        else:
            tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

        reader = metric_reader or PeriodicExportingMetricReader(
            OTLPMetricExporter()
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        meter = meter_provider.get_meter(settings.service_name, settings.service_version)
    else:
        meter = metrics.get_meter(
            settings.service_name,
            settings.service_version,
        )

    return TelemetryRuntime(
        settings=settings,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        request_counter=meter.create_counter(
            "saas.http.server.request.count",
            description="Number of HTTP requests handled by the API",
            unit="{request}",
        ),
        request_duration=meter.create_histogram(
            "saas.http.server.request.duration",
            description="Duration of HTTP requests handled by the API",
            unit="s",
        ),
    )


def configure_request_logging(settings: TelemetrySettings) -> None:
    logger = logging.getLogger(REQUEST_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(getattr(handler, "_saas_json_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            StructuredRequestFormatter(
                settings.service_name,
                settings.service_version,
            )
        )
        setattr(handler, "_saas_json_handler", True)
        logger.addHandler(handler)


class StructuredRequestFormatter(logging.Formatter):
    def __init__(self, service_name: str, service_version: str):
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version

    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        trace_id = (
            f"{span_context.trace_id:032x}"
            if span_context.is_valid
            else getattr(record, "trace_id", None)
        )
        span_id = (
            f"{span_context.span_id:016x}"
            if span_context.is_valid
            else getattr(record, "span_id", None)
        )
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                timezone.utc,
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": self.service_name,
            "service_version": self.service_version,
            "message": record.getMessage(),
            "route": getattr(record, "route", "unmatched"),
            "method": getattr(record, "method", None),
            "status": getattr(record, "status", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "trace_id": trace_id,
            "span_id": span_id,
            "tenant_id": getattr(record, "tenant_id", None),
        }
        return json.dumps(payload, separators=(",", ":"))


class RequestTelemetryMiddleware:
    def __init__(self, app: ASGIApp, telemetry: TelemetryRuntime):
        self.app = app
        self.telemetry = telemetry
        self.logger = logging.getLogger(REQUEST_LOGGER_NAME)

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500
        route = "unmatched"

        async def send_with_observability(message: Message) -> None:
            nonlocal status_code, route
            if message["type"] == "http.response.start":
                status_code = message["status"]
                matched_route = scope.get("route")
                route = getattr(matched_route, "path", "unmatched")
            await send(message)

        try:
            await self.app(scope, receive, send_with_observability)
        finally:
            duration_seconds = perf_counter() - started_at
            state = scope.get("state", {})
            tenant_id = state.get("tenant_id") if isinstance(state, dict) else None
            span_context = trace.get_current_span().get_span_context()
            trace_id = (
                f"{span_context.trace_id:032x}"
                if span_context.is_valid
                else state.get("otel_trace_id")
            )
            span_id = (
                f"{span_context.span_id:016x}"
                if span_context.is_valid
                else state.get("otel_span_id")
            )
            attributes = {
                "http.route": route,
                "http.request.method": scope["method"],
                "http.response.status_code": status_code,
            }
            if tenant_id is not None:
                attributes["tenant.id"] = tenant_id

            self.telemetry.request_counter.add(1, attributes)
            self.telemetry.request_duration.record(duration_seconds, attributes)
            self.logger.info(
                "http_request",
                extra={
                    "route": route,
                    "method": scope["method"],
                    "status": status_code,
                    "duration_ms": round(duration_seconds * 1000, 3),
                    "tenant_id": tenant_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                },
            )
