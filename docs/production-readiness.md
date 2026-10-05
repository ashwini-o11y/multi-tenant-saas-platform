# Production Readiness

This is a planning checklist for future evaluation, not a statement that the platform is production-ready. The project is a portfolio/POC and is not suitable for real banking workloads or customer data.

Before any production-like claim, define and verify at least:

- Identity, authorization, tenant isolation, secret handling, and security review
- Data classification, encryption, retention, deletion, backup, and restore
- Availability targets, SLIs/SLOs, error budgets, alert ownership, and on-call response
- Repeatable builds, image provenance, dependency checks, staged releases, and rollback
- Capacity limits, load tests, cost ownership, and per-tenant cost assumptions
- Incident response, auditability, recovery objectives, and tested DR/BCP procedures

Readiness is evidence-based and applies to a specific environment and scope. Completing a roadmap milestone alone does not establish production readiness.