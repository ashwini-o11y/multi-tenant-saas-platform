# Release Management

## Release identity

A release is the API container built from a validated repository revision and published to ACR as:

```text
<acr-login-server>/multi-tenant-saas/api:<full-git-sha>
```

The full Git commit SHA is the immutable-by-convention artifact identity. M7 does not deploy `latest`; the optional M3 `dev` tag remains a mutable convenience tag and must not be used for deployment. The SHA identifies source and image tag; it is not a content digest, so registry digest verification remains useful for stronger supply-chain assurance.

## Promotion

The main-branch build workflow validates and publishes an image. Deployment is a separate manually dispatched workflow targeting GitHub Environment `dev`; the operator supplies an already-published full Git SHA. This keeps the deployed artifact explicit and allows the same image to be promoted later without rebuilding it. Environment-specific Kubernetes configuration is maintained in `kubernetes/overlays/dev/`, layered on the shared base.

## Rollout and rollback

The dev overlay uses Deployment `RollingUpdate` with `maxUnavailable: 0` and `maxSurge: 1`; readiness probes gate replacement readiness. The deployment script waits for `kubectl rollout status` with a timeout and automatically runs `kubectl rollout undo` when an existing deployment fails its rollout, then checks the rollback status. Initial installation has no previous ReplicaSet to restore; a failed first rollout is reported as failed.

Manual recovery is also available:

```bash
kubectl rollout history deployment/multi-tenant-saas-api -n mt-saas
kubectl rollout undo deployment/multi-tenant-saas-api -n mt-saas
kubectl rollout status deployment/multi-tenant-saas-api -n mt-saas --timeout=180s
```

Inspect the exact image and pod-template release annotation:

```bash
kubectl get deployment multi-tenant-saas-api -n mt-saas \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="api")].image}{"\n"}{.spec.template.metadata.annotations.app\.kubernetes\.io/version}{"\n"}'
```

One replica does not provide production-grade zero-downtime delivery, and local SQLite/`emptyDir` storage is not shared across replicas. The rollout mechanics demonstrate readiness gating and rollback, not production availability or canary analysis. See [cicd.md](./cicd.md) for GitHub/Azure setup and operational steps.