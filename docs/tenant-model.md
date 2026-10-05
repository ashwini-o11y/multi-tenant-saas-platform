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

M6 persists tenant status (`ACTIVE`, `SUSPENDED`, or `DEACTIVATED`) and UTC creation/update timestamps. Tenants can be onboarded through the admin API, and business requests are allowed only while a tenant is active. Suspension and deactivation retain tenant and business records; see [tenant-lifecycle.md](./tenant-lifecycle.md) for the allowed transitions and API details.

**M6 implements application-level tenant lifecycle management. Automated AKS tenant provisioning is a future platform milestone.** Tenant namespace/configuration identifiers are planning metadata only; M6 does not create namespaces, quotas, policies, or other cloud resources. The admin API is unauthenticated and is not a production authorization boundary. Auditing, retention policy, identity-backed administration, automated provisioning, and tenant self-service remain future work.