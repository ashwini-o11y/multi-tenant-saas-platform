# Multi-Tenant Banking SaaS Platform

A single evolving fictional banking SaaS application for demonstrating incremental multi-tenant application and platform architecture.

## Project Scope

This is a fictional portfolio/proof-of-concept (POC) application, not a production banking system. No real banking or customer data is used. Do not use it for real financial activity, sensitive data, or production workloads.

## Current Milestone: M8.3 - SLI/SLO and Error Budgets

```text
Terraform -> Azure Resource Group + VNet + ACR + AKS
                                      |
                                      v
                          Kubernetes API Deployment
                                      |
                                      v
                          FastAPI + SQLite
                              | OTLP
                              v
                       OpenTelemetry Collector
                              |
                              v
                 Grafana LGTM local observability backend
```

The M1 application provides a small tenant-aware customer and transaction view for `bank-a`, `bank-b`, and `bank-c`. The API validates a centralized tenant context and uses tenant-scoped data access. **X-Tenant-ID is a simplified tenant selector for this portfolio POC and is not an authentication or authorization mechanism.** Anyone able to reach this demo can select a tenant; identity-backed tenant authentication and authorization remain future work.

## Run Locally

From the repository root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the API and test dependencies:

```bash
python -m pip install -r application/api/requirements.txt
```

Initialize and seed the local SQLite database with deterministic fictional data:

```bash
cd application/api
python -m app.seed
```

Start the API from `application/api`:

```bash
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

Run the tests from the repository root in another terminal with the virtual environment active:

```bash
python -m pytest application/api/tests
```

Serve the plain HTML frontend in another terminal from the repository root:

```bash
python -m http.server 5500 --directory application/frontend
```

Open `http://127.0.0.1:5500`. Keep the API and frontend servers running while using the page. The default database is `application/api/data/banking_saas.sqlite3`; it is local and ignored by Git. The seed command is safe to rerun and does not replace existing tenant data.

## Run with Docker

Build and start the API container:

```bash
docker compose build
docker compose up -d
docker compose ps
curl http://localhost:8000/health
```

SQLite is stored in the `banking_data` Docker named volume, so its data survives API container recreation and `docker compose down`. To stop the stack:

```bash
docker compose down
```

The named volume is intentionally retained when the stack stops. Removing it with `docker compose down -v` deletes the local SQLite data.

## M8.2 - Local Observability Stack

Start the API, OpenTelemetry Collector, and Grafana LGTM backend together with `docker compose up -d --build`. The API exports OTLP over HTTP to the collector and does not wait for either telemetry service to start. The backend UI is at `http://localhost:3000`; Collector OTLP and health endpoints are available on `localhost:4317`, `localhost:4318`, and `localhost:13133`. These host ports bind to loopback only.

Run representative tenant requests with `curl -H 'X-Tenant-ID: bank-a' http://localhost:8000/api/v1/tenant`, and inspect metrics and traces in Grafana Explore. Structured request logs remain available in API container stdout; application log records are not yet exported over OTLP. The complete signal flow, configuration, and limitations are documented in [docs/observability.md](docs/observability.md).

M8.3 adds machine-readable 30-day SLO definitions and a deterministic Python calculation library. It reuses the existing request count/duration telemetry; it does not add instrumentation, query the backend automatically, or introduce alerting. See [observability/slo/slo.yaml](observability/slo/slo.yaml) and [docs/observability.md](docs/observability.md).

## Azure Container Registry

Prerequisites: Azure CLI, Docker, an Azure subscription, permission to create the resource group and registry, and `AcrPush` access to the registry. Sign in and select the subscription, then create the development resource group and Basic registry (choose a globally unique lowercase registry name):

```bash
az login
export AZURE_SUBSCRIPTION_ID="<subscription-id>"
export AZURE_LOCATION="<azure-region>"
export RESOURCE_GROUP="rg-mt-saas-dev"
export ACR_NAME="acrmtsaas<unique-suffix>"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --output table
az group create --name "$RESOURCE_GROUP" --location "$AZURE_LOCATION"
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled false
az acr login --name "$ACR_NAME"
```

The reusable script builds from the existing M2 Dockerfile, pushes the full Git SHA tag, and also pushes `dev` by default. Set `PUSH_DEV_TAG=false` to omit the mutable convenience tag:

```bash
export ACR_NAME
./scripts/acr-build-push.sh
```

Verify the repository, tags, and digest, then pull by immutable SHA:

```bash
az acr repository list --name "$ACR_NAME" --output table
az acr repository show-tags --name "$ACR_NAME" --repository multi-tenant-saas/api --output table
az acr repository show --name "$ACR_NAME" --image "multi-tenant-saas/api:<git-sha>" --query digest --output tsv
docker pull "$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)/multi-tenant-saas/api:<git-sha>"
```

This M3 workflow publishes the image used by the M4 AKS deployment; it does not itself deploy to AKS. For resource naming, tagging, digest identity, verification, and cleanup details, see [docs/azure-container-registry.md](docs/azure-container-registry.md).

## M4 - Terraform + AKS Foundation

M4 provisions a development Azure platform with Terraform and deploys the existing API using Kubernetes manifests. It uses the AKS kubelet managed identity with `AcrPull`; it does not use ACR admin credentials or static image pull secrets. Follow the end-to-end prerequisites, authentication, Terraform, image publishing, deployment, verification, cleanup, and limitations guide in [infrastructure/terraform/README.md](infrastructure/terraform/README.md).

The API's SQLite database is container-local and ephemeral in AKS. This is only a transitional demonstration, not persistent or production storage; persistence is deferred to a later milestone. AKS and its Azure networking and compute resources incur costs.

## M5 - Strong Tenant Isolation & Platform Controls

M5 centralizes tenant context and tenant-scoped repository access, adds tenant-filtered resource reads with cross-tenant isolation tests, and hardens the Kubernetes workload with a dedicated permissionless ServiceAccount, resource governance, NetworkPolicy, and non-root container settings. See [docs/tenant-isolation.md](docs/tenant-isolation.md) for the trust boundary, controls, and limitations. The M4 AKS configuration enables Azure network policy enforcement so the Kubernetes policies are effective.

## M6 - Tenant Onboarding & Lifecycle

M6 adds administrative tenant creation, lookup, listing, suspension, activation, and deactivation endpoints backed by persisted lifecycle state and explicit transition rules. Suspended and deactivated tenants cannot access business APIs; tenant records and business data are retained. The control-plane API is intentionally unauthenticated and is not a production authorization boundary. **M6 implements application-level tenant lifecycle management. Automated AKS tenant provisioning is a future platform milestone.** See [docs/tenant-lifecycle.md](docs/tenant-lifecycle.md) for endpoints, transitions, and limitations.

## M7 - SaaS CI/CD + Progressive Delivery

M7 adds pull-request/main CI, Git-SHA-tagged ACR publishing from `main`, and a separately dispatched dev deployment that consumes a selected immutable image tag. The dev rollout uses Kubernetes readiness gates and automatic rollback on timeout; deployment release identity is recorded in pod-template metadata. See [docs/cicd.md](docs/cicd.md) and [docs/release-management.md](docs/release-management.md).

## M8 - Observability + SLO

M8.1 added FastAPI OpenTelemetry traces/metrics and structured correlated stdout request logs. M8.2 implements a local OpenTelemetry Collector and Grafana LGTM backend, plus Kubernetes-ready manifests. Host-side component health and API checks passed, but container-to-container TCP timeouts in this Codespaces Docker environment prevented end-to-end telemetry ingestion from being verified; no Kubernetes context was available for cluster validation. See [docs/observability.md](docs/observability.md) for evidence. M8.3 will define SLIs, SLOs, and error budgets; M8.4 will add reliability alerting.

## Milestone Roadmap

1. **M1 - Application:** frontend, FastAPI, SQLite, tenant context, and tenant-scoped data access.
2. **M2 - Docker:** package this same application in containers.
3. **M3 - ACR:** publish versioned images to Azure Container Registry.
4. **M4 - Terraform + AKS Foundation:** provision Azure networking, ACR, AKS, and deploy the existing API.
5. **M5 - Strong Tenant Isolation & Platform Controls:** centralize tenant-scoped API access and add Kubernetes workload isolation and governance.
6. **M6 - Tenant Onboarding & Lifecycle:** onboard tenants through an application control plane and enforce persisted lifecycle states.
7. **M7 - CI/CD + Progressive Delivery:** validate changes, publish Git-SHA artifacts, and deploy with health-gated rollout and rollback.
8. **M8 - Observability + SLO:** M8.1 establishes OpenTelemetry signals and structured logs; later increments will define SLIs/SLOs, error budgets, and alerting.
9. **M9 - FinOps + Capacity:** model tenant costs and plan capacity from observed demand.
10. **M10 - Multi-Region DR/BCP:** define and test disaster recovery and business continuity.
11. **M11 - SARI:** explore a human-approved detect-to-verify remediation workflow.

Azure, ACR, AKS, and Docker support the implemented early milestones; PostgreSQL, Kafka or another message broker, identity-backed tenant authentication, multi-region recovery, and SARI remain future capabilities. See [docs/development-roadmap.md](docs/development-roadmap.md) for the milestone sequence and [docs/application-architecture.md](docs/application-architecture.md) for the intended application evolution.