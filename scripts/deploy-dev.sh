#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ACR_LOGIN_SERVER:-}" ]]; then
  printf 'ACR_LOGIN_SERVER must be set to the target Azure Container Registry login server.\n' >&2
  exit 2
fi

if [[ ! "${IMAGE_TAG:-}" =~ ^([a-f0-9]{40}|[a-f0-9]{64})$ ]]; then
  printf 'IMAGE_TAG must be a full 40- or 64-character lowercase Git SHA.\n' >&2
  exit 2
fi

for command_name in kubectl kustomize; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 2
  fi
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf -- "$WORK_DIR"' EXIT

mkdir -p "$WORK_DIR/kubernetes"
cp -R "$REPO_ROOT/kubernetes/base" "$WORK_DIR/kubernetes/base"
mkdir -p "$WORK_DIR/kubernetes/overlays"
cp -R "$REPO_ROOT/kubernetes/overlays/dev" "$WORK_DIR/kubernetes/overlays/dev"

OVERLAY_DIR="$WORK_DIR/kubernetes/overlays/dev"
IMAGE_REPOSITORY="$ACR_LOGIN_SERVER/multi-tenant-saas/api"
IMAGE_REFERENCE="$IMAGE_REPOSITORY:$IMAGE_TAG"
DEPLOYMENT="deployment/multi-tenant-saas-api"
NAMESPACE="mt-saas"

(cd "$OVERLAY_DIR" && kustomize edit set configmap deployment-release --from-literal="APP_VERSION=$IMAGE_TAG")
(cd "$OVERLAY_DIR" && kustomize edit set image "multi-tenant-saas/api=$IMAGE_REFERENCE")

PREVIOUS_DEPLOYMENT="$(
  kubectl get deployment multi-tenant-saas-api \
    --namespace "$NAMESPACE" \
    --ignore-not-found \
    --output name
)"
PREVIOUS_REVISION=""
if [[ -n "$PREVIOUS_DEPLOYMENT" ]]; then
  kubectl rollout status "$DEPLOYMENT" \
    --namespace "$NAMESPACE" \
    --timeout=180s
  PREVIOUS_REVISION="$(
    kubectl get "$DEPLOYMENT" \
      --namespace "$NAMESPACE" \
      --output 'jsonpath={.metadata.annotations.deployment\.kubernetes\.io/revision}'
  )"
fi

rollback_on_failure() {
  local current_revision

  if [[ -z "$PREVIOUS_DEPLOYMENT" || -z "$PREVIOUS_REVISION" ]]; then
    printf 'No previous healthy Deployment revision is available for automatic rollback.\n' >&2
    return 1
  fi

  current_revision="$(
    kubectl get "$DEPLOYMENT" \
      --namespace "$NAMESPACE" \
      --output 'jsonpath={.metadata.annotations.deployment\.kubernetes\.io/revision}'
  )"
  if [[ "$current_revision" == "$PREVIOUS_REVISION" ]]; then
    printf 'The failed release did not create a new Deployment revision to roll back.\n' >&2
    return 1
  fi

  printf 'Rolling back failed release to previously healthy revision %s.\n' \
    "$PREVIOUS_REVISION" >&2
  kubectl rollout undo "$DEPLOYMENT" \
    --namespace "$NAMESPACE" \
    --to-revision="$PREVIOUS_REVISION"
  kubectl rollout status "$DEPLOYMENT" \
    --namespace "$NAMESPACE" \
    --timeout=180s
}

if ! kubectl apply -k "$OVERLAY_DIR"; then
  printf 'Kubernetes apply failed for image %s.\n' "$IMAGE_REFERENCE" >&2
  if [[ -n "$PREVIOUS_DEPLOYMENT" ]]; then
    rollback_on_failure
  fi
  exit 1
fi

if ! kubectl rollout status "$DEPLOYMENT" \
  --namespace "$NAMESPACE" \
  --timeout=180s; then
  printf 'Release %s failed readiness-gated rollout.\n' "$IMAGE_TAG" >&2
  rollback_on_failure
  exit 1
fi

printf 'Deployment %s is healthy with image %s.\n' "$DEPLOYMENT" "$IMAGE_REFERENCE"
