# Observability

M8.1 instruments the FastAPI service with OpenTelemetry HTTP traces and metrics plus structured request logs. M8.2 routes OTLP telemetry through an OpenTelemetry Collector to a local Grafana LGTM backend and provides Kubernetes-ready manifests. Telemetry export is asynchronous and is not a prerequisite for application startup or request handling.

## Architecture

```text
FastAPI API -- OTLP/HTTP --> OpenTelemetry Collector -- OTLP/gRPC --> Grafana LGTM
    |                                  |                               |
    |                                  |                               +-- Prometheus-compatible metrics
    |                                  |                               +-- Tempo traces
    |                                  |                               +-- Loki logs (OTLP input supported)
    +-- structured JSON request logs to stdout
```

The Collector receives OTLP/gRPC and OTLP/HTTP, applies memory limiting and batching, and exports signals to the backend. The backend is the open-source `grafana/otel-lgtm` distribution: a compact local stack integrating Grafana with Prometheus-compatible metrics storage, Tempo traces, and Loki logs. It was selected to make all three signals inspectable through one local UI rather than introducing separately managed backend services. No custom Grafana dashboards are included.

Collector exporters are the boundary between instrumentation and storage. A later deployment can replace the backend and change exporter configuration without changing tenant handling or application instrumentation; this milestone does not integrate Dynatrace, Splunk, or any other enterprise vendor.

## Local startup and ports

From the repository root:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
curl http://localhost:8000/health
```

Services and host ports:

| Service / endpoint | Compose host port | Kubernetes Service port | Purpose |
| --- | ---: | ---: | --- |
| API HTTP | 8000 | 8000 | FastAPI HTTP API |
| Collector OTLP/gRPC | 4317 | 4317 | OTLP receiver |
| Collector OTLP/HTTP | 4318 | 4318 | OTLP receiver (the API uses this) |
| Collector health | 13133 | 13133 | Collector health endpoint |
| LGTM UI | 3000 | 3000 | Grafana UI and signal exploration |
| LGTM OTLP/gRPC | Not published | 4317 | Internal backend ingestion from Collector |
| LGTM OTLP/HTTP | Not published | 4318 | Internal backend OTLP receiver |

All Collector and backend host ports bind to loopback. Inside Compose the API uses `http://collector:4318`; the Collector exports to `observability-backend:4317`. API startup has no Compose dependency on either service. Stop the stack with `docker compose down`. The backend has no named volume, so its local telemetry is ephemeral when its container is removed; the existing SQLite `banking_data` volume remains independent.

Open `http://localhost:3000` to use Grafana Explore. Select the Prometheus-compatible datasource to find the `saas.http.server.request.count` and `saas.http.server.request.duration` metrics (Prometheus may normalize punctuation in metric names). Select Tempo and search for service `multi-tenant-saas-api` to inspect request spans. Loki is available for log queries if OTLP logs are sent to the Collector. Existing application request logs are available through `docker compose logs api`.

For a quick exercise, make a health request and a valid tenant request:

```bash
curl http://localhost:8000/health
curl -H 'X-Tenant-ID: bank-a' http://localhost:8000/api/v1/tenant
curl -H 'X-Tenant-ID: unknown-bank' http://localhost:8000/api/v1/tenant
curl -H 'X-Tenant-ID: bank-a' http://localhost:8000/api/v1/customers
curl -H 'X-Tenant-ID: bank-a' http://localhost:8000/api/v1/transactions
```

Inspect telemetry in Grafana Explore and structured stdout events with `docker compose logs api`. Metrics and spans use the existing matched-route, method, status, service, version, environment, and validated tenant attributes.

## Runtime validation evidence

The Compose runtime was started and the following host-side checks succeeded:

- `GET http://localhost:8000/health` returned `{"status":"ok"}`.
- `GET http://localhost:13133/` returned Collector status `Server available`.
- `GET http://localhost:3000/api/health` returned Grafana health information.
- Requests to the `bank-a` customers and transactions routes succeeded.
- Docker network inspection confirmed the `multi-tenant-saas-platform_default` bridge network (`172.18.0.0/16`) with API `172.18.0.3`, Collector `172.18.0.4`, and backend `172.18.0.2`.
- `docker compose exec api getent hosts collector` resolved `collector` to `172.18.0.4`.

Despite healthy services and successful DNS resolution, a direct TCP connection from the API container to Collector `172.18.0.4:4318` timed out. Collector logs also report `i/o timeout` while dialing the backend OTLP/gRPC endpoint `172.18.0.2:4317`. Therefore, end-to-end telemetry ingestion into LGTM was **not verified**. The observed behavior is an environment-specific Docker/Codespaces container-to-container TCP connectivity limitation, not evidence that OTLP data reached the backend.

The intended service-DNS architecture remains API → Collector OTLP/HTTP on `:4318` → Grafana OTEL-LGTM OTLP/gRPC on `:4317`. It was intentionally not changed to use host networking, localhost between containers, host addresses, or a disabled Collector/backend. The API remained healthy and customer/transaction routes remained usable despite the telemetry-path timeouts.

Kubernetes base, dev overlay, and observability manifests render with Kustomize. Kubernetes end-to-end validation remains pending: there is no current Kubernetes context/cluster available in this environment.

## Configuration

| Variable | Default / local value | Description |
| --- | --- | --- |
| `OTEL_ENABLED` | `false` standalone; `true` in Compose and Kubernetes | Enables SDK trace and metric providers. |
| `OTEL_SERVICE_NAME` | `multi-tenant-saas-api` | OpenTelemetry service identity. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | API exporter protocol; this application currently supports OTLP/HTTP protobuf. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Exporter default when enabled | API's OTLP/HTTP endpoint; set to the Collector service, not a backend URL. |
| `OTEL_EXPORTER_OTLP_HEADERS` | unset | Optional standard OTLP exporter headers; do not store secrets in repository configuration. |
| `APP_VERSION` | `1.0.0` | Exported as `service.version`. |
| `DEPLOYMENT_ENVIRONMENT` | `local` | Exported as `deployment.environment.name`. |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Exporter default | Export timeout in milliseconds; local Compose uses 3000. |
| `OTEL_BACKEND_OTLP_ENDPOINT` | Compose/Kubernetes service address | Collector's OTLP/gRPC backend destination. |

The Collector configuration is in [collector-config.yaml](../kubernetes/observability/collector-config.yaml). The endpoint is supplied through an environment variable in both Compose and Kubernetes. The API can still run independently of Compose; telemetry remains disabled by default unless explicitly enabled and given a runtime endpoint.

## Telemetry signals

### Metrics

The API retains the M8.1 request count and duration instruments:

- `saas.http.server.request.count`
- `saas.http.server.request.duration`

The metric attributes include `http.route`, `http.request.method`, and `http.response.status_code`; `tenant.id` is present only when a valid active tenant context exists. The Collector preserves these attributes. Route templates are used instead of raw URLs to avoid query-string and path-value cardinality.

### Traces

Automatic FastAPI instrumentation emits HTTP server spans through OTLP/HTTP. Resource attributes include `service.name`, `service.version`, and `deployment.environment.name`. Spans include the matched route, method, status, and `tenant.id` only after tenant validation. Existing sanitization remains in place: raw URLs and query strings are not exported, sensitive headers are sanitized, and request bodies are not captured.

### Logs

The application continues to emit its existing structured JSON request events to stdout. They include timestamp, level, service/version, route, method, status, duration, trace/span IDs, and the validated tenant ID where available. The Collector's OTLP logs pipeline and LGTM OTLP ingestion are ready for OTLP log records, but M8.1 does not export its Python request logger through OTLP. Shipping container stdout consistently across local Docker and Kubernetes would require adding log collection/runtime-specific plumbing or changing the application logging pipeline; that is intentionally deferred rather than creating a second log format. Use container stdout for current request logs.

## Tenant attribution and privacy

Telemetry tenant attribution comes only from the validated tenant context. The raw `X-Tenant-ID` header is not trusted as an identity: a valid active tenant receives its canonical `tenant.id`, unknown or inactive tenants do not, and `/health` has no tenant attribute. Existing tenant isolation behavior is unchanged.

The application does not export authorization headers, cookies, passwords, tokens, request bodies, or arbitrary query strings. Tenant identifiers remain sensitive operational data; protect backend access and retention in shared environments. No credentials or production endpoints are included in the Collector, Compose, or Kubernetes configuration.

## Failure behavior

- **Collector unavailable:** the application still starts and serves requests. OTLP exporters run asynchronously with bounded timeouts; exports may be retried or dropped by the SDK when unavailable.
- **Backend unavailable:** the Collector remains independently running and retries transient exporter failures according to the Collector exporter retry policy. Telemetry may eventually be dropped after retry limits; this does not gate API traffic.
- **Telemetry disabled:** standalone application use defaults to `OTEL_ENABLED=false`; trace and metric SDK exporters are not initialized. Structured request logs continue on stdout.

The local backend and Collector are demonstration infrastructure, not a durable or highly available monitoring service. Backend data is ephemeral in this Compose/Kubernetes setup.

## Kubernetes

`kubernetes/observability/` contains the Collector ConfigMap generator, Deployment and Service, LGTM Deployment and Service, and signal-path NetworkPolicies. These resources are included from the existing `kubernetes/base` kustomization in namespace `mt-saas`. Render them with:

```bash
kubectl kustomize kubernetes/base
kubectl kustomize kubernetes/overlays/dev
```

The API sends OTLP/HTTP to the in-namespace Collector service. NetworkPolicies allow only the API-to-Collector and Collector-to-backend telemetry paths plus Collector DNS. The backend is a ClusterIP service; inspect its UI locally with `kubectl -n mt-saas port-forward service/observability-backend 3000:3000`. Workloads use non-root identities, dropped capabilities, resource bounds, health probes, no service-account token, and no privileged or host-network access. The backend uses ephemeral storage and the local manifests do not deploy to Azure.

## Roadmap

- **M8.3:** introduce SLIs, SLOs, and error budgets.
- **M8.4:** introduce reliability alerting.

Neither milestone is implemented here. This increment does not add dashboards, alert rules, alertmanager, incident automation, or integrations with enterprise backends.
