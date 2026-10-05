# Azure Container Registry

## Scope

M3 establishes a repeatable path for building the existing M2 API image and publishing it to Azure Container Registry (ACR). ACR will be the image registry for a future AKS deployment. This milestone does not create AKS, Kubernetes manifests, Terraform, GitHub Actions, or any other deployment pipeline. No Azure resource or image is created by this documentation alone.

## Resource Design

Use a fictional development environment name and supply account-specific values at runtime. Do not store subscription IDs, credentials, access tokens, or secrets in the repository.

| Resource | Convention/example | Notes |
| --- | --- | --- |
| Azure subscription | `$AZURE_SUBSCRIPTION_ID` | Selected by the operator; never commit the value. |
| Resource group | `rg-mt-saas-dev` | Contains the development registry. |
| ACR name | `acrmtsaas<unique-suffix>` | Replace the placeholder with lowercase letters/numbers to produce a globally unique 5-50 character registry name. ACR names cannot contain hyphens. |
| SKU | `Basic` | Suitable for this learning/POC workflow; review Azure limits and cost before use. |
| Region | `$AZURE_LOCATION`, such as `eastus` | Choose an Azure region supported by the subscription and appropriate for the development resource group. |
| Repository/image | `multi-tenant-saas/api` | One repository for the existing API image. |

The ACR registry name is globally unique across Azure. Check availability with `az acr check-name --name "$ACR_NAME"` before creating it.

## Prerequisites and Azure CLI

Install Docker and Azure CLI using their official installation guidance. Docker must be running. The user creating resources needs permission to create a resource group and ACR; the identity pushing images needs `AcrPush` on the registry. Use Azure CLI user authentication for this workflow; a service principal is not required.

```bash
az version
az login
az account list --output table

export AZURE_SUBSCRIPTION_ID="<subscription-id>"
export AZURE_LOCATION="<azure-region>"
export RESOURCE_GROUP="rg-mt-saas-dev"
export ACR_NAME="acrmtsaas<unique-suffix>"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query '{name:name,state:state,isDefault:isDefault}' --output table
az acr check-name --name "$ACR_NAME"
az group create --name "$RESOURCE_GROUP" --location "$AZURE_LOCATION"
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled false
```

Retrieve the login server and authenticate Docker using the signed-in Azure identity:

```bash
ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)"
az acr login --name "$ACR_NAME"
printf 'Registry login server: %s\n' "$ACR_LOGIN_SERVER"
```

Keep credential output out of logs and repository files. Do not enable or use the ACR admin account for this workflow.

## Image Tags and Identity

The image is named `multi-tenant-saas/api`. The push helper uses the full Git commit SHA as an immutable-by-convention tag, for example:

```text
<login-server>/multi-tenant-saas/api:<40-character-git-sha>
```

The helper also pushes a mutable `dev` tag by default for convenient development pulls. Set `PUSH_DEV_TAG=false` to skip it. Never use `latest` as the only identifying tag.

A Git SHA tag records which source revision was used to build an image, which makes later deployment references, audits, and rollback selection reproducible. A tag is still a name and can be moved if registry permissions allow it. The image digest (for example, `sha256:...`) identifies the exact content-addressed manifest and is the strongest immutable image identity. Record and, where supported, deploy by digest when exact artifact identity is required.

## Build and Push

From the repository root, set `ACR_NAME` and run:

```bash
export ACR_NAME="<your-acr-name>"
./scripts/acr-build-push.sh
```

The script validates its inputs and tools, reads the current full Git SHA, obtains the registry login server, builds using `application/api/Dockerfile` with `application/api` as the build context, applies the SHA tag, optionally applies `dev`, authenticates with `az acr login`, and pushes the selected tags. It prints the resulting image references. It does not create or delete Azure resources.

Equivalent build steps, if performed manually, are:

```bash
GIT_SHA="$(git rev-parse HEAD)"
ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)"
IMAGE_REF="$ACR_LOGIN_SERVER/multi-tenant-saas/api:$GIT_SHA"
docker build -f application/api/Dockerfile -t "$IMAGE_REF" application/api
az acr login --name "$ACR_NAME"
docker push "$IMAGE_REF"
```

## Verify and Pull

```bash
az acr repository list --name "$ACR_NAME" --output table
az acr repository show-tags \
  --name "$ACR_NAME" \
  --repository multi-tenant-saas/api \
  --output table

GIT_SHA="$(git rev-parse HEAD)"
az acr repository show \
  --name "$ACR_NAME" \
  --image "multi-tenant-saas/api:$GIT_SHA" \
  --query digest \
  --output tsv

ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)"
docker pull "$ACR_LOGIN_SERVER/multi-tenant-saas/api:$GIT_SHA"
```

The repository and tag commands verify registry metadata; `az acr repository show` returns the manifest metadata, including its digest. Pulling by the SHA tag confirms the tagged image is available to Docker. Do not infer successful publication from a local build alone.

## Cleanup

Remove only local image tags when finished with a local copy:

```bash
docker image rm "$ACR_LOGIN_SERVER/multi-tenant-saas/api:$GIT_SHA"
docker image rm "$ACR_LOGIN_SERVER/multi-tenant-saas/api:dev" 2>/dev/null || true
```

To remove the Azure resources, first verify the resource group contains only resources intended for deletion, then:

```bash
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
```

Deleting the resource group permanently removes its resources and registry images. This operation is intentionally not part of the build/push script.