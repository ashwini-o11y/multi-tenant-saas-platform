# Development Roadmap

The milestones evolve one fictional banking SaaS application. They are ordered to establish application behavior before adding the infrastructure and operating practices that support it. Scope may be refined as learning emerges; later milestones are not current capabilities.

| Milestone | Focus | Intended outcome |
| --- | --- | --- |
| M1 | Application | A locally usable frontend, FastAPI API, and SQLite database; implement application-level `X-Tenant-ID` context and tenant-scoped data access with cross-tenant read protection. The header is not authentication. |
| M2 | Docker | Build and run the same application in containers with documented local configuration. |
| M3 | ACR | Publish versioned application images to Azure Container Registry. |
| M4 | Terraform + AKS Foundation | Provision Azure networking, ACR, AKS, and deploy the existing API. |
| M5 | Strong Tenant Isolation & Platform Controls | Centralize tenant context and data access; add Kubernetes workload security, resource governance, and network policy controls. |
| M6 | Tenant Onboarding & Lifecycle | Onboard tenants through an application control plane, persist lifecycle state, enforce allowed transitions, and retain tenant data on suspension/deactivation. Automated AKS provisioning remains future work. |
| M7 | SaaS CI/CD + Progressive Delivery | Validate pull requests and main, publish immutable Git-SHA images to ACR, and manually promote selected artifacts to dev with health-gated rollout and rollback. |
| M8.1 | Observability foundation | Instrument HTTP traces/metrics and structured correlated request logs. |
| M8.2 | Collector + backend | Implemented: Collector, Grafana LGTM, Compose wiring, and Kubernetes manifests. Local component/API health and manifest rendering passed; end-to-end telemetry and Kubernetes runtime validation remain pending due to environment networking/context limitations. |
| M8.3 | Service objectives | Implemented: machine-readable availability, success-rate, and latency objectives; deterministic SLO/error-budget/burn-rate calculations; and unit tests. |
| M8.4 | Reliability alerting | Implemented: deterministic fast-/slow-burn multi-window policies with error-budget-derived thresholds, explicit no-data/recovery states, and structured alert evaluations. Backend rule provisioning and notification delivery remain future work. |
| M9 | FinOps + Capacity | Estimate cost per tenant, track meaningful usage, and plan capacity based on observed demand. |
| M10 | Multi-Region DR/BCP | Define recovery objectives and validate backup, restore, failover, and business continuity procedures. |
| M11 | SARI | Add a bounded workflow for detection, correlation, diagnosis, remediation recommendation, human approval, remediation, and verification. |

## Sequencing Notes

- M1 must be useful locally and does not depend on Azure.
- M1 already establishes application-level tenant context and tenant-scoped data access; the header selector is not authentication.
- M2-M4 introduce packaging and deployment foundations before production-style operations.
- M5 strengthens tenant isolation through application data-access boundaries and platform controls; it does not mark the beginning of tenant scoping.
- M6 implements application-level tenant lifecycle management. Automated AKS tenant provisioning is a future platform milestone. Its unauthenticated admin API is not a production authorization boundary.
- M8.1 provides telemetry instrumentation and structured request logs. M8.2 implementation is complete: OTLP metrics and traces are configured through a Collector to Grafana LGTM, with structured logs remaining on stdout. Compose service health and API behavior were verified, but Codespaces container-to-container TCP timeouts prevented end-to-end ingestion verification; no Kubernetes cluster context was available for runtime validation. M8.3 defines and calculates SLIs/SLOs from supplied observations. M8.4 implements policy evaluation in the calculation layer; end-to-end backend alert evaluation and notification delivery are not claimed.
- PostgreSQL and Kafka or another message broker are possible future application capabilities, not M1 dependencies.
- M7-M10 build delivery and operational confidence around the same application.
- M11 depends on trustworthy signals, controlled permissions, auditability, and human approval. It does not authorize unreviewed automated changes.

No AKS cluster, Azure resources, PostgreSQL, Kafka or another message broker, multi-region implementation, AI, or SARI are part of M1. These roadmap items are future capabilities and are not claimed as implemented.