# Tenant Model

## Initial Tenants

The fictional platform begins with three independent customer organizations identified as `bank-a`, `bank-b`, and `bank-c` (Bank A, Bank B, and Bank C). Additional tenants can be onboarded later without creating a separate application or codebase for each bank.

## Tenant-Owned Data

Business records belong to a tenant and must have an unambiguous tenant association. Requests that read, create, update, or delete tenant-owned records are scoped to the caller's authorized tenant. Cross-tenant access is denied by default. Platform-wide operational records (for example, tenant registry metadata) are distinct from tenant-owned business data and require their own access controls.

Never use real customer or banking data in this POC.

## Tenant Context

The API requires `X-Tenant-ID` as a deliberately simplified tenant selector. A missing header receives HTTP 400, and an unknown tenant receives HTTP 404. **X-Tenant-ID is a simplified tenant selector for this portfolio POC and is not an authentication or authorization mechanism.** It does not establish identity or prove that a caller is entitled to act for that tenant. The API validates and normalizes the selected ID against known tenants and uses the resulting server-side tenant context for tenant-owned queries. A tenant ID in request data must never override this context. Future identity-backed authentication and authorization must bind tenant selection to the caller's entitlements before the context is trusted.

## Isolation

The application provides tenant context and tenant-scoped data access, with tests for same-tenant access and denied cross-tenant reads. M5 adds a tenant-scoped repository boundary and AKS namespace/workload controls. These are application-level tenant isolation and Kubernetes workload-level controls, respectively; neither creates a hard per-tenant infrastructure boundary. Stronger separation (such as per-schema, per-database, or dedicated deployments) may be evaluated against security requirements, cost, and operational complexity.

## Tenant-Specific Configuration

Tenant configuration may include supported product settings and operational limits. It is managed separately from business records, validated against an application-defined schema, and resolved using the authorized tenant context. Secrets are not stored as ordinary tenant configuration and must use an appropriate secret-management mechanism when one is introduced. Defaults and platform-wide settings remain distinct from tenant overrides.

## Tenant Lifecycle

The expected lifecycle is:

1. **Provision:** create a tenant record, assign a stable identifier, and apply validated defaults.
2. **Configure:** set permitted tenant-specific options and establish authorized users.
3. **Operate:** serve tenant-scoped requests and monitor tenant-level health and usage where available.
4. **Change:** validate and audit configuration changes without changing another tenant's state.
5. **Suspend or offboard:** restrict access and handle data retention or deletion according to an explicitly documented policy.

Automated onboarding, audit controls, retention policy, and tenant self-service are future work, not M1 features. M2 and later cloud or platform capabilities do not change the M1 limitation that `X-Tenant-ID` is not authentication.