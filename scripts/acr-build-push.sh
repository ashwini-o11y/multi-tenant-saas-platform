#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ACR_NAME:-}" ]]; then
  printf 'ACR_NAME must be set to the target Azure Container Registry name.\n' >&2
  exit 2
fi

for command_name in az docker git; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 2
  fi
done

PUSH_DEV_TAG="${PUSH_DEV_TAG:-true}"
if [[ "$PUSH_DEV_TAG" != "true" && "$PUSH_DEV_TAG" != "false" ]]; then
  printf 'PUSH_DEV_TAG must be either true or false.\n' >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
IMAGE_REPOSITORY="multi-tenant-saas/api"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"

az account show --output none
ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)"
if [[ -z "$ACR_LOGIN_SERVER" ]]; then
  printf 'Could not resolve the ACR login server for registry %s.\n' "$ACR_NAME" >&2
  exit 1
fi

SHA_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_REPOSITORY:$GIT_SHA"
DEV_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_REPOSITORY:dev"

docker build \
  --file "$REPO_ROOT/application/api/Dockerfile" \
  --tag "$SHA_IMAGE" \
  "$REPO_ROOT/application/api"

if [[ "$PUSH_DEV_TAG" == "true" ]]; then
  docker tag "$SHA_IMAGE" "$DEV_IMAGE"
fi

az acr login --name "$ACR_NAME"
docker push "$SHA_IMAGE"
printf 'Pushed image: %s\n' "$SHA_IMAGE"

if [[ "$PUSH_DEV_TAG" == "true" ]]; then
  docker push "$DEV_IMAGE"
  printf 'Pushed image: %s\n' "$DEV_IMAGE"
fi