# M6 Tenant Onboarding and Lifecycle

M6 adds application-level tenant onboarding and lifecycle management on the existing SQLite-backed tenant model. It does not change the M4 AKS architecture or provision Azure/Kubernetes resources.

**M6 implements application-level tenant lifecycle management. Automated AKS tenant provisioning is a future platform milestone.**

## Tenant states and transitions

Each tenant has a stable identifier, name, controlled status, UTC `created_at` and `updated_at` timestamps, and platform-provisioning identifiers. The status is one of:

- `ACTIVE`: tenant business APIs are available.
- `SUSPENDED`: tenant remains present, but business APIs are blocked. An administrator may activate it or deactivate it.
- `DEACTIVATED`: tenant remains present, but business APIs are blocked. Deactivation is terminal in M6.

Allowed lifecycle transitions:

| Current status | Operation | Result |
| --- | --- | --- |
| `ACTIVE` | suspend | `SUSPENDED` |
| `SUSPENDED` | activate | `ACTIVE` |
| `ACTIVE` | deactivate | `DEACTIVATED` |
| `SUSPENDED` | deactivate | `DEACTIVATED` |

All other lifecycle transitions return HTTP 409. Repeating a transition is not treated as success.

## Administrative API

The control-plane API is available under `/api/v1/admin/tenants`:

| Method and path | Behavior |
| --- | --- |
| `POST /api/v1/admin/tenants` | Create an `ACTIVE` tenant; returns HTTP 201. Body: `{"tenant_id":"bank-d","name":"Bank D"}`. |
| `GET /api/v1/admin/tenants` | List tenants. |
| `GET /api/v1/admin/tenants/{tenant_id}` | Retrieve a tenant or return HTTP 404. |
| `POST /api/v1/admin/tenants/{tenant_id}/suspend` | Suspend an active tenant. |
| `POST /api/v1/admin/tenants/{tenant_id}/activate` | Activate a suspended tenant. |
| `POST /api/v1/admin/tenants/{tenant_id}/deactivate` | Deactivate an active or suspended tenant. |

Tenant IDs must be 3-50 lowercase letters and digits, with single hyphens separating non-empty segments. Names are trimmed and must not be empty. The server selects the initial status; client-supplied extra fields such as `status` are rejected. Duplicate creation returns HTTP 409 and does not overwrite the existing tenant. Validation failures return HTTP 422.

Responses include `tenant_id`, `name`, `status`, ISO-compatible UTC timestamps, `platform_namespace_id`, and `platform_configuration_id`.

### Administrative trust boundary

These admin endpoints are intentionally unauthenticated in M6. **They are not an authentication or authorization boundary and must not be exposed to untrusted callers or used for production tenant administration.** No API keys, passwords, OAuth/OIDC/JWT, or external identity provider are added. Identity-backed authorization is future work.

## Business API interaction

The existing centralized tenant context continues to validate `X-Tenant-ID`. Unknown and missing tenant behavior is unchanged. An active tenant can use tenant-scoped customer and transaction APIs. Suspended or deactivated tenants receive HTTP 403 from business APIs; admins can still inspect or transition their records through the control-plane endpoints.

The `X-Tenant-ID` header remains a caller-controlled selector, not authentication. Lifecycle state supplements but does not replace tenant-scoped repository filtering or identity-backed authorization.

## Data retention

Suspending or deactivating changes only tenant status and `updated_at`. It does not delete or mutate tenant records, customer records, transaction records, or their identifiers. Reactivating a suspended tenant restores business API access to the retained data. Deactivated tenants cannot be reactivated in M6.

## Platform provisioning contract

Onboarding persists deterministic `platform_namespace_id` and `platform_configuration_id` metadata (for example, `mt-bank-d` and `tenant-bank-d-config`). These values identify intended future resources only; M6 does not create a Kubernetes namespace or resource, call Azure, deploy workloads, or claim platform readiness.

A later provisioning workflow can consume an onboarded tenant record and explicitly request namespace, quota, network policy, tenant configuration, application deployment, and observability setup, then report readiness. That automation is outside M6.

## Persistence and limitations

SQLite remains the database. Initialization adds lifecycle columns to the existing tenant table and defaults existing tenant rows to `ACTIVE`, preserving the current `bank-a`, `bank-b`, and `bank-c` data. No migration framework or new database engine is introduced.

The lifecycle API has no authenticated admin identity, audit log, approval workflow, data-retention/deletion policy, asynchronous provisioning, or tenant-specific AKS resources. SQLite persistence and the M5 application-level selector limitations remain unchanged.
