# Development Roadmap

The milestones evolve one fictional banking SaaS application. They are ordered to establish application behavior before adding the infrastructure and operating practices that support it. Scope may be refined as learning emerges; later milestones are not current capabilities.

| Milestone | Focus | Intended outcome |
| --- | --- | --- |
| M1 | Application | A locally usable frontend, FastAPI API, and SQLite database; implement application-level `X-Tenant-ID` context and tenant-scoped data access with cross-tenant read protection. The header is not authentication. |
| M2 | Docker | Build and run the same application in containers with documented local configuration. |
| M3 | ACR | Publish versioned application images to Azure Container Registry. |
| M4 | Terraform + AKS Foundation | Provision Azure networking, ACR, AKS, and deploy the existing API. |
| M5 | Strong Tenant Isolation & Platform Controls | Centralize tenant context and data access; add Kubernetes workload security, resource governance, and network policy controls. |
| M6 | Tenant Onboarding | Define and implement a controlled tenant provisioning and lifecycle workflow. |
| M7 | CI/CD + Progressive Delivery | Automate validation and delivery with staged rollout, canary evaluation, and rollback. |
| M8 | Observability + SLO | Add OpenTelemetry signals, dashboards, alerts, SLIs, SLOs, and error-budget practices. |
| M9 | FinOps + Capacity | Estimate cost per tenant, track meaningful usage, and plan capacity based on observed demand. |
| M10 | Multi-Region DR/BCP | Define recovery objectives and validate backup, restore, failover, and business continuity procedures. |
| M11 | SARI | Add a bounded workflow for detection, correlation, diagnosis, remediation recommendation, human approval, remediation, and verification. |

## Sequencing Notes

- M1 must be useful locally and does not depend on Azure.
- M1 already establishes application-level tenant context and tenant-scoped data access; the header selector is not authentication.
- M2-M4 introduce packaging and deployment foundations before production-style operations.
- M5 strengthens tenant isolation through application data-access boundaries and platform controls; it does not mark the beginning of tenant scoping.
- PostgreSQL and Kafka or another message broker are possible future application capabilities, not M1 dependencies.
- M7-M10 build delivery and operational confidence around the same application.
- M11 depends on trustworthy signals, controlled permissions, auditability, and human approval. It does not authorize unreviewed automated changes.

No AKS cluster, Azure resources, PostgreSQL, Kafka or another message broker, multi-region implementation, AI, or SARI are part of M1. These roadmap items are future capabilities and are not claimed as implemented.