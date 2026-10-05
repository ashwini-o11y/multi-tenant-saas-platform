# Platform Architecture

## Intent

This document describes the intended long-term direction of one fictional banking SaaS platform. M1 is a local frontend, FastAPI API, and SQLite database with application-level tenant context and tenant-scoped queries. This document is an architectural guide, not a description of deployed infrastructure. Extend the same application in place as each milestone needs it.

## Logical View

```text
Bank-A / Bank-B / Bank-C / future tenants
                    |
          Frontend and tenant context
                    |
         Ingress or API gateway (later)
                    |
             API and services
              /           \
        Workers         Message broker
              \           /
         PostgreSQL / cache / object storage
                    |
      Telemetry, security, and operations
```

The diagram represents logical responsibilities. It does not prescribe that every box be a separate process or deployment. Early milestones deliberately consolidate components.

## Main Responsibilities

- **Frontend:** user-facing workflows; the M1 interface selects a tenant and sends its identifier as `X-Tenant-ID`. This selector is not authentication.
- **API and services:** own domain behavior and enforce tenant-scoped access. M1 validates the selected tenant and filters tenant-owned queries; authentication and authorization are future capabilities.
- **Workers and broker:** may support asynchronous work when the application has a concrete need for it. Neither is part of M1; Kafka or another message broker is future work.
- **Data stores:** persist tenant-owned data. Access paths must scope reads and writes to the authorized tenant.
- **Platform and delivery:** later provide container builds, deployment, configuration, secrets handling, and progressive release controls.
- **Operations:** later collect traces, metrics, and logs; define SLOs and alerts; and support cost, capacity, incident, and recovery practices.

## Tenant and Security Boundaries

In M1, `X-Tenant-ID` is a deliberately simplified tenant selector, not proof of identity or authorization. The API validates it against known tenants and filters tenant-owned data queries server-side; frontend filtering is never a security control. Future authentication must bind tenant context to an authorized identity before it is trusted. Tenant-specific configuration remains distinct from tenant-owned business data and platform-wide configuration.

M1 provides application-level tenant context and tenant-scoped data access. M5 is intended to add stronger production-style isolation controls at the platform/infrastructure level. Evaluate stronger database, schema, namespace, or deployment isolation only when security needs and operating costs justify it. Logical scoping alone is not hard infrastructure isolation.

## Incremental Evolution

M1 is a frontend, FastAPI, and SQLite application. Later milestones may introduce Docker, Azure and ACR, AKS, PostgreSQL, caching, asynchronous workers, and Kafka or another message broker as the use cases and deployment model mature. Multi-region recovery and SARI are also future milestones, not prerequisites for the first application slice.

## Quality Attributes

- Keep tenant boundaries explicit, testable, and deny-by-default.
- Prefer simple operational choices until scale or reliability goals show a need to change them.
- Keep configuration and secrets out of source control.
- Make changes observable and releases reversible as delivery capabilities are introduced.
- Document recovery objectives and validate recovery procedures before claiming readiness.

## Non-Goals

This POC is not a regulated banking product, a financial ledger, or production infrastructure. It must not contain real banking data or credentials. Architecture statements about future services and controls are plans, not implemented guarantees.