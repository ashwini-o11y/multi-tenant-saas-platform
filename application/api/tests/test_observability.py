import json
import logging
from io import StringIO

from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.database import get_db
from app.main import create_app
from app.observability import (
    REQUEST_LOGGER_NAME,
    SERVICE_NAME,
    StructuredRequestFormatter,
    TelemetrySettings,
    TelemetryRuntime,
    configure_telemetry,
)


def telemetry_settings(enabled=False):
    return TelemetrySettings(
        enabled=enabled,
        service_name=SERVICE_NAME,
        service_version="test-version",
        environment="test",
        protocol="http/protobuf",
    )


def create_observed_client(telemetry, session_factory):
    application = create_app(telemetry)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    return TestClient(application)


def test_telemetry_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)

    telemetry = configure_telemetry()

    assert telemetry.settings.enabled is False
    assert telemetry.tracer_provider is None
    assert telemetry.meter_provider is None


def test_health_works_with_telemetry_disabled(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_enabled_telemetry_starts_without_collector(
    monkeypatch, database_session_factory
):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "200")
    telemetry = configure_telemetry()

    with create_observed_client(telemetry, database_session_factory) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tenant_attributes_require_validated_context_and_skip_health(
    database_session_factory,
):
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    telemetry = configure_telemetry(
        telemetry_settings(enabled=True),
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )

    with create_observed_client(telemetry, database_session_factory) as client:
        valid_response = client.get(
            "/api/v1/tenant?account=never-export-this",
            headers={
                "X-Tenant-ID": "BANK-A",
                "Authorization": "Bearer never-export-this-token",
            },
        )
        health_response = client.get("/health")
        unknown_response = client.get(
            "/api/v1/tenant", headers={"X-Tenant-ID": "bank-untrusted"}
        )
        metrics_data = metric_reader.get_metrics_data()

    assert valid_response.status_code == 200
    assert health_response.status_code == 200
    assert unknown_response.status_code == 404

    spans = span_exporter.get_finished_spans()
    tenant_span = next(
        span
        for span in spans
        if span.attributes.get("http.route") == "/api/v1/tenant"
        and span.attributes.get("tenant.id") == "bank-a"
    )
    assert tenant_span.attributes["tenant.id"] == "bank-a"
    assert all(
        "tenant.id" not in span.attributes
        for span in spans
        if span.attributes.get("http.route") == "/health"
        or span.attributes.get("http.route") == "/api/v1/tenant"
        and span.attributes.get("http.response.status_code") == 404
    )
    assert all(
        "never-export-this" not in str(span.attributes)
        for span in spans
    )

    metric_attributes = [
        data_point.attributes
        for resource_metric in metrics_data.resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
        for data_point in metric.data.data_points
    ]
    assert any(attributes.get("tenant.id") == "bank-a" for attributes in metric_attributes)
    assert any(
        attributes.get("http.route") == "/health"
        and "tenant.id" not in attributes
        for attributes in metric_attributes
    )
    assert metrics_data.resource_metrics[0].resource.attributes["service.name"] == SERVICE_NAME
    assert (
        metrics_data.resource_metrics[0].resource.attributes["service.version"]
        == "test-version"
    )


def test_request_logs_are_structured_correlated_and_do_not_capture_secrets(
    database_session_factory,
):
    telemetry = configure_telemetry(
        telemetry_settings(enabled=True),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    logger = logging.getLogger(REQUEST_LOGGER_NAME)
    original_handlers = logger.handlers[:]
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(
        StructuredRequestFormatter(SERVICE_NAME, "test-version")
    )
    logger.handlers = [handler]

    try:
        with create_observed_client(telemetry, database_session_factory) as client:
            response = client.get(
                "/api/v1/customers?account=never-export-this-token",
                headers={
                    "X-Tenant-ID": "bank-a",
                    "Authorization": "Bearer do-not-log-this-token",
                },
            )
    finally:
        logger.handlers = original_handlers
        handler.close()

    assert response.status_code == 200
    record = json.loads(output.getvalue())
    assert record["service"] == SERVICE_NAME
    assert record["service_version"] == "test-version"
    assert record["route"] == "/api/v1/customers"
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["tenant_id"] == "bank-a"
    assert record["trace_id"]
    assert record["span_id"]
    assert "never-export-this-token" not in output.getvalue()


def test_structured_formatter_uses_only_active_trace_context():
    telemetry = configure_telemetry(
        telemetry_settings(enabled=True),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    formatter = StructuredRequestFormatter(SERVICE_NAME, "test-version")
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "http_request",
        (),
        None,
    )

    span = telemetry.tracer_provider.get_tracer("test").start_span("test")
    try:
        with trace.use_span(span):
            output = json.loads(formatter.format(record))
    finally:
        span.end()
        telemetry.shutdown()

    assert output["trace_id"] == f"{span.get_span_context().trace_id:032x}"
    assert output["span_id"] == f"{span.get_span_context().span_id:016x}"
