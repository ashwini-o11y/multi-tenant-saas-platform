# M5 Tenant Isolation and Platform Controls

M5 strengthens the existing API and AKS foundation without changing the database engine or introducing external identity. The API's application-level tenant boundary and Kubernetes' workload-level controls address different risks; namespace controls do not replace per-request tenant authorization.

## Application-level tenant isolation

### Tenant context and trust boundary

The API supports the fictional tenants `bank-a`, `bank-b`, and `bank-c`. Every tenant API route obtains a `TenantContext` through the shared `get_tenant_context` dependency. It trims and lowercases the supplied ID, verifies it against the tenant table, and returns the canonical tenant ID and tenant record to the route.

**X-Tenant-ID is a simplified tenant selector for this portfolio POC and is not an authentication or authorization mechanism.** A caller can select any known tenant because M5 does not establish caller identity or bind tenant selection to entitlements. Do not use this mechanism for real users or production data. Identity-backed tenant authentication and authorization are future work; OAuth/OIDC/JWT and external identity providers are not part of M5.

### Authorization boundary and scoped data access

Routes use `TenantScopedRepository` for list and ID-based reads of customers and transactions. The repository includes the current tenant ID in every query, including resource-by-ID queries. A record belonging to another tenant therefore has the same response as a nonexistent record (`404`); the API does not disclose its existence.

The shared tenant-context dependency is required by the tenant, customer, and transaction routes. The health endpoint is intentionally tenant-independent and returns no tenant-owned data. New tenant-facing routes must use the shared context and tenant-scoped repository rather than querying tenant-owned models directly.

### Fail-closed behavior and tests

- Missing or blank tenant context returns HTTP 400.
- An unknown tenant returns HTTP 404.
- Valid tenant IDs proceed with the canonical ID.
- Customer and transaction collection reads include only the selected tenant's records.
- Customer and transaction reads by ID return HTTP 404 for another tenant's resource.

Deterministic fixtures seed the three fictional tenants. `application/api/tests/test_tenant_isolation.py` contains explicit positive and negative tenant-isolation tests.

## Kubernetes/platform-level workload controls

Kubernetes controls restrict and govern the API workload in the `mt-saas` namespace. They do not create a separate namespace or cluster per tenant and do not replace application-level tenant scoping.

### ServiceAccount and RBAC

The Deployment uses the dedicated `multi-tenant-saas-api` ServiceAccount. Its API token is not mounted (`automountServiceAccountToken: false`), and the Deployment also disables automatic token mounting. The application does not need Kubernetes API access, so no Role, RoleBinding, ClusterRole, or ClusterRoleBinding is created.

### ResourceQuota and LimitRange

`mt-saas-workload-quota` caps the namespace at five pods, 1 CPU / 1 GiB total requested resources, and 2 CPU / 2 GiB total resource limits. `mt-saas-container-limits` supplies defaults for containers that omit resource values and constrains their minimum and maximum. The API Deployment retains its explicit 100m CPU / 128Mi memory requests and 500m CPU / 512Mi memory limits.

### NetworkPolicy

`multi-tenant-saas-api-default-deny` selects the API pods and isolates both ingress and egress. It allows TCP port 8000 from pods in `mt-saas` for the internal ClusterIP Service, and DNS over TCP/UDP port 53 to kube-dns in `kube-system`. Other ingress and egress are denied by policy. There is no public ingress. Future ingress or observability components must receive deliberate, narrowly scoped policy rules.

NetworkPolicy enforcement depends on the cluster's network-policy implementation. The M4 AKS network profile is configured with Azure network policy enforcement so these policies are active on the target AKS cluster. Other clusters must likewise use a compatible, enabled CNI policy provider.

### Configuration and container security

The `multi-tenant-saas-api-config` ConfigMap holds the non-sensitive `DATABASE_PATH=/data/app.db` setting. No Kubernetes Secret is needed or created.

The pod runs as the image's existing non-root UID/GID 10001, sets `fsGroup` 10001 for writable `/data`, and uses the `RuntimeDefault` seccomp profile. The container cannot escalate privileges and drops all Linux capabilities. The API retains its ephemeral writable SQLite `emptyDir`. `readOnlyRootFilesystem` is not enabled in M5; it requires further runtime verification of all writable paths and is not needed to establish the controls above.

## Current limitations

- `X-Tenant-ID` is caller-controlled and is not authentication or authorization. A caller can impersonate any known fictional tenant.
- SQLite remains a demo database. In AKS, data in `/data` is ephemeral, local to each pod, and lost when that pod is replaced.
- The NetworkPolicy applies to the API pods rather than creating tenant-specific network isolation. It allows same-namespace sources to reach the API service port and depends on CNI enforcement.
- Resource values and quotas are development examples, not capacity planning.
- No public ingress, external identity, per-tenant cluster/network boundary, secrets integration, or production persistence is provided.
