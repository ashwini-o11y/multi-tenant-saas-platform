# Cost Model

FinOps and capacity planning are planned for M9. No Azure resources or cost telemetry are currently defined. This document describes how a future estimate can remain useful without implying precision the evidence does not support.

## Cost Dimensions

Separate shared platform costs (such as control plane, ingress, shared monitoring, and baseline compute) from usage-sensitive costs attributable to tenant activity (such as request volume, storage, data transfer, and background work). Record the allocation method and distinguish measured charges from modeled estimates.

## Cost per Tenant

A future cost-per-tenant view should state its period, currency, included services, allocation rules, and treatment of shared or unallocated costs. Where direct attribution is unavailable, use a documented allocation proxy and label it as an estimate. Avoid presenting tenant cost as a precise bill unless metering and billing semantics justify it.

## Capacity

Capacity planning should use observed workload shape, service limits, headroom, growth assumptions, and load-test results. Revisit assumptions when traffic, tenant count, or architecture changes. Cost optimization must not silently weaken tenant isolation, reliability objectives, or data protection.