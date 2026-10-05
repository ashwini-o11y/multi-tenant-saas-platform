# Tenant Model

## Initial Tenants

The fictional platform begins with three independent customer organizations identified as `bank-a`, `bank-b`, and `bank-c` (Bank A, Bank B, and Bank C). Additional tenants can be onboarded later without creating a separate application or codebase for each bank.

## Tenant-Owned Data

Business records belong to a tenant and must have an unambiguous tenant association. Requests that read, create, update, or delete tenant-owned records are scoped to the caller's authorized tenant. Cross-tenant access is denied by default. Platform-wide operational records (for example, tenant registry metadata) are distinct from tenant-owned business data and require their own access controls.

Never use real customer or banking data in this POC.

## Tenant Context

In M1, the API requires `X-Tenant-ID` as a deliberately simplified tenant selector. A missing header receives HTTP 400, and an unknown tenant receives HTTP 404. This mechanism is **not authentication**: it does not establish identity or prove that a caller is entitled to act for that tenant. The API validates the selected ID against known tenants and uses that server-side tenant context for all tenant-owned queries. A tenant ID in request data must never override this context. Future authentication and authorization must bind tenant selection to the caller's entitlements before the context is trusted.

## Isolation

M1 provides application-level tenant context and explicit `tenant_id` filtering for tenant-owned API data access, with tests for same-tenant access and denied cross-tenant reads. The frontend is not a security boundary. M5 is intended to add stronger production-style isolation controls at the platform/infrastructure level. Stronger separation (such as per-schema, per-database, or dedicated deployments) may be evaluated against security requirements, cost, and operational complexity; no hard infrastructure isolation is claimed for M1.

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