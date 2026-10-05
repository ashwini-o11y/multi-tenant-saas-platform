# Application Architecture

The application is one evolving product, not a set of milestone-specific demos. Add boundaries when they clarify ownership or solve an actual need; do not split components merely to match a target diagram.

## M1: Application

```text
Frontend -> API -> SQLite
```

M1 is implemented as a plain HTML/CSS/JavaScript frontend calling a single FastAPI API backed by SQLite. The UI sends `X-Tenant-ID` for `bank-a`, `bank-b`, or `bank-c`; a reusable API dependency validates the tenant, and tenant-owned customer and transaction queries filter by `tenant_id`. This is application-level tenant scoping only, not authentication. The tenant selector is not trusted as identity, and request data cannot override the validated server-side context. Tests use an isolated SQLite database. Do not add a broker, distributed services, or cloud infrastructure in M1.

## Later: Scale the Application Shape

```text
Frontend -> API/services -> PostgreSQL/cache/Kafka or another message broker/workers
```

As requirements emerge, the API may gain cohesive internal services or separately deployable services. PostgreSQL can replace or supplement SQLite for a later deployment; a cache is added only for a measured need; Kafka or another message broker and workers may support asynchronous workflows. These are future capabilities, not part of M1. Keep synchronous request handling and asynchronous work explicit, and make tenant context available to each operation.

These components are introduced in stages. This diagram is not a requirement to adopt them all at once.

## Eventually: Operated Platform

```text
Frontend -> ingress/gateway -> services -> workers/message broker -> data stores
```

The eventual platform may route traffic through an ingress or gateway to tenant-aware application services. Workers consume queued work and use the appropriate data stores. Azure, AKS, multi-region recovery, and SARI are future capabilities. Deployment, identity, network policy, telemetry, release controls, and recovery practices surround the application rather than becoming separate demo products.

## Evolution Principles

- Preserve one product and one domain model across milestones.
- Introduce new infrastructure only alongside a concrete application or operational requirement.
- Keep persistence and external integrations behind narrow interfaces where that materially eases evolution.
- Make authorization and tenant scoping part of API behavior, not a frontend convention.
- Keep local development useful; cloud services must not be required for the initial application milestone.
- Do not claim availability, isolation, or recovery guarantees until they are implemented and tested.