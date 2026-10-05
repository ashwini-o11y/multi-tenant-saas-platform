# Multi-Tenant Banking SaaS Platform

A single evolving fictional banking SaaS application for demonstrating incremental multi-tenant application and platform architecture.

## Project Scope

This is a fictional portfolio/proof-of-concept (POC) application, not a production banking system. No real banking or customer data is used. Do not use it for real financial activity, sensitive data, or production workloads.

## Current Milestone: M1 - Application

```text
Frontend
	|
	v
FastAPI
	|
	v
SQLite
```

The M1 application provides a small tenant-aware customer and transaction view for `bank-a`, `bank-b`, and `bank-c`. The API requires `X-Tenant-ID` and filters tenant-owned database queries on the server. This is application-level tenant context and tenant-scoped data access, **not authentication**. Anyone able to reach this local demo can select a tenant; there is no identity verification or production security boundary. Stronger security and platform/infrastructure isolation are future work.

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

ACR is the image registry intended for a later AKS milestone; this does not deploy to AKS. For resource naming, tagging, digest identity, verification, and cleanup details, see [docs/azure-container-registry.md](docs/azure-container-registry.md).

## Milestone Roadmap

1. **M1 - Application:** frontend, FastAPI, SQLite, tenant context, and tenant-scoped data access.
2. **M2 - Docker:** package this same application in containers.
3. **M3 - ACR:** publish versioned images to Azure Container Registry.
4. **M4 - AKS:** deploy the application to Azure Kubernetes Service.
5. **M5 - Strong Tenant Isolation & Platform Controls:** add stronger production-style isolation controls at the platform/infrastructure level.
6. **M6 - Tenant Onboarding:** introduce a controlled tenant provisioning and lifecycle workflow.
7. **M7 - CI/CD + Progressive Delivery:** automate validation, staged rollout, canary evaluation, and rollback.
8. **M8 - Observability + SLO:** add telemetry, dashboards, alerts, SLIs, SLOs, and error-budget practices.
9. **M9 - FinOps + Capacity:** model tenant costs and plan capacity from observed demand.
10. **M10 - Multi-Region DR/BCP:** define and test disaster recovery and business continuity.
11. **M11 - SARI:** explore a human-approved detect-to-verify remediation workflow.

Azure, ACR, AKS, Docker, PostgreSQL, Kafka or another message broker, multi-region recovery, and SARI are future capabilities; they are not part of M1. See [docs/development-roadmap.md](docs/development-roadmap.md) for the milestone sequence and [docs/application-architecture.md](docs/application-architecture.md) for the intended application evolution.