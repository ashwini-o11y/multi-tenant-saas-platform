# M4 Terraform + AKS Foundation

This configuration creates a small development resource group, virtual network and AKS subnet, Basic Azure Container Registry, and AKS cluster. AKS uses Azure CNI Overlay and a system-assigned identity; the kubelet identity receives `AcrPull` on the registry. Terraform provisions Azure infrastructure only. Kubernetes resources are managed separately from `kubernetes/base`.

AKS compute and Azure networking incur costs. Review the plan before applying and destroy the development resources when they are no longer needed.

## Prerequisites

- Terraform 1.6.x and Azure CLI
- `kubectl` with Kustomize support (`kubectl kustomize`)
- Docker, for building and pushing the API image
- An Azure subscription and permissions to create the resource group, network, registry, AKS cluster, and role assignment

## Azure authentication and permissions

Sign in with Azure CLI and select the subscription to use:

```bash
az login
az account set --subscription "<subscription-id>"
az account show
```

AzureRM 4.x also requires the subscription ID for its provider configuration. Set it from the selected CLI account in the current shell:

```bash
export ARM_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
```

The signed-in principal needs sufficient Azure RBAC permissions to create and manage these resources, including permission to assign the `AcrPull` role to the AKS kubelet identity (typically `Owner` or `User Access Administrator` together with resource creation permissions). No client secret or ACR admin credential is used.

## Variables and Terraform workflow

Copy the safe example values and choose a globally unique ACR name (5-50 lowercase letters or numbers):

```bash
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
```

Edit `terraform.tfvars` to configure the Azure location, resource group, ACR, AKS name and sizing, network CIDRs, environment, and API image handoff. The `api_image` input is exposed as an output for operator reference; Kubernetes manifests remain a separate deployment layer and are configured independently below. The defaults use one `Standard_D2s_v3` node and the Azure-selected Kubernetes version when `kubernetes_version` is null. Set a Kubernetes version explicitly if the selected Azure region or policy requires it. Terraform variables are described in [variables.tf](./variables.tf).

Initialize, review, and apply:

```bash
terraform -chdir=infrastructure/terraform init
terraform -chdir=infrastructure/terraform plan
terraform -chdir=infrastructure/terraform apply
```

The configuration uses local state for this learning milestone. State files are ignored by Git; do not share or commit them. A secure remote state backend, state locking, and access controls are future production concerns.

## Build and push the API image

After `apply`, get the registry name and login server:

```bash
ACR_NAME="$(terraform -chdir=infrastructure/terraform output -raw acr_name)"
ACR_LOGIN_SERVER="$(terraform -chdir=infrastructure/terraform output -raw acr_login_server)"
```

Reuse the M3 script to build the existing API Dockerfile and push its Git SHA tag to `multi-tenant-saas/api`:

```bash
export ACR_NAME
./scripts/acr-build-push.sh
GIT_SHA="$(git rev-parse HEAD)"
API_IMAGE="${ACR_LOGIN_SERVER}/multi-tenant-saas/api:${GIT_SHA}"
printf 'API image: %s\n' "$API_IMAGE"
```

The deployment uses the immutable-by-convention Git SHA tag, not `latest` or the optional mutable `dev` convenience tag.

## Connect to AKS and deploy

Retrieve the cluster and resource group from Terraform outputs, then configure the current `kubectl` context:

```bash
RESOURCE_GROUP="$(terraform -chdir=infrastructure/terraform output -raw resource_group_name)"
AKS_NAME="$(terraform -chdir=infrastructure/terraform output -raw aks_cluster_name)"
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$AKS_NAME"
```

Before deploying, edit `kubernetes/base/kustomization.yaml`: set `images[0].newName` to `${ACR_LOGIN_SERVER}/multi-tenant-saas/api` and `images[0].newTag` to the `GIT_SHA` printed by the build workflow. The checked-in placeholders are intentionally not deployable. Then render and apply the manifests:

```bash
kubectl kustomize kubernetes/base
kubectl apply -k kubernetes/base
```

AKS pulls from ACR using its kubelet managed identity and the `AcrPull` role assignment created by Terraform; no image pull secret is required. The Kubernetes namespace is `mt-saas`; the API Deployment and internal `ClusterIP` Service are `multi-tenant-saas-api`.

## Verify the API

Check the rollout and service:

```bash
kubectl get pods -n mt-saas
kubectl get svc -n mt-saas
```

Forward the service port locally and call the existing health endpoint:

```bash
kubectl port-forward -n mt-saas service/multi-tenant-saas-api 8000:8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Cleanup

This permanently deletes the Azure resources managed by this Terraform configuration. Remove the Kubernetes workload first if desired, and inspect the Terraform plan carefully before confirming:

```bash
kubectl delete -k kubernetes/base
terraform -chdir=infrastructure/terraform destroy
```

Terraform destroy does not remove local Terraform state.

## Known M4 limitations

- The API uses SQLite at `/data/app.db` on an `emptyDir`. Data is ephemeral and is lost when the pod is replaced; each replica would have its own isolated database. This is only a temporary M4 demonstration, not production persistence. Database service and persistent storage are deferred to later work.
- No public ingress is provided. The service is internal to the cluster; use `kubectl port-forward` for this milestone.
- The Basic registry, single-node development cluster, local Terraform state, and minimal networking are not production architecture.
- Azure resources can incur charges while they exist. Review Azure pricing and delete development resources when finished.
