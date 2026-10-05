# M7 CI/CD and Progressive Delivery

M7 separates safe validation, image publication, and environment deployment. Pull requests receive CI only and never receive Azure credentials. Main-branch commits are validated before a SHA-tagged API image is published to ACR. Deployment is a separately dispatched promotion to the `dev` environment using an explicit already-published SHA.

## CI pipeline

`.github/workflows/ci.yml` runs on pull requests, pushes to `main`, and as a reusable workflow for image publication. It runs from the repository root and:

1. Sets up Python 3.13, installs `application/api/requirements.txt`, and runs `pytest -q`.
2. Checks shell syntax, Docker Compose configuration, Kubernetes base/dev Kustomize rendering, and commit diff whitespace.
3. Runs Terraform formatting and validation without an Azure login or backend.
4. Builds the API with the existing `application/api/Dockerfile`.
5. Lints GitHub Actions workflow syntax.

CI has read-only repository permissions, does not receive secrets or OIDC tokens, and does not publish images or deploy from pull requests.

## Immutable image build and ACR publishing

`.github/workflows/build-and-publish.yml` runs only after pushes to `main`. It first calls the reusable CI workflow; the publish job can run only when CI succeeds. It then uses GitHub OIDC federation to Azure, builds the existing API Dockerfile, and pushes:

```text
<acr-login-server>/multi-tenant-saas/api:<full-git-sha>
```

No `latest` tag is published or deployed. The optional M3 `dev` tag is not used by this workflow. SHA tags are immutable by convention; inspect the registry digest when stronger byte-for-byte artifact identity is needed.

## Deploying the dev environment

Deployment is intentionally separate from build and is never triggered by a pull request or arbitrary Docker build. Once a main-branch image is published, dispatch **Deploy API to dev** from the `main` branch in GitHub Actions and provide its full 40-character Git SHA in `image_tag`. The workflow checks out main, authenticates to Azure through OIDC, selects the configured AKS cluster, resolves the ACR login server, and calls `scripts/deploy-dev.sh`.

The script validates the SHA format, copies the Kustomize base and dev overlay to a temporary directory, updates the Kustomize image and release metadata sources, then applies the rendered resources. Kustomize `replacements` writes `app.kubernetes.io/version=<sha>` into the Deployment pod template before apply. Image and release annotation therefore change together in one Deployment revision; there is no post-apply patch that could create another revision. The checked-in overlay is not modified. The dev overlay layers on `kubernetes/base`; the Namespace object is deliberately excluded from routine dev deployment, while the existing namespace, ServiceAccount, quotas, LimitRange, NetworkPolicy, ConfigMap, Service, probes, resource bounds, and container security settings remain otherwise preserved.

The API Deployment uses a Kubernetes `RollingUpdate` strategy with `maxUnavailable: 0` and `maxSurge: 1`. Kubernetes readiness probes on `/health` gate availability of the updated pod. The script waits up to 180 seconds for `kubectl rollout status`; a failed rollout of an existing Deployment triggers `kubectl rollout undo` followed by a status check of the restored revision. A first-ever rollout has no previous ReplicaSet to restore; it fails and reports that rollback is unavailable. Manual rollback steps are in [release-management.md](./release-management.md).

Deployment release identification is available from both the image SHA tag and pod-template annotation:

```bash
kubectl get deployment multi-tenant-saas-api -n mt-saas \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="api")].image}{"\n"}{.spec.template.metadata.annotations.app\.kubernetes\.io/version}{"\n"}'
```

## GitHub and Azure configuration

Configure these repository **Actions variables** (not secrets):

| Variable | Purpose |
| --- | --- |
| `ACR_NAME` | Name of the M4 Azure Container Registry. |
| `AZURE_TENANT_ID` | Azure tenant used for OIDC sign-in. |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription containing ACR and AKS. |
| `AZURE_CLIENT_ID` | Federated application/client ID for image publishing. |
| `AZURE_DEPLOY_CLIENT_ID` | Federated application/client ID for dev deployment. |
| `AKS_RESOURCE_GROUP` | Resource group containing the development AKS cluster. |
| `AKS_CLUSTER_NAME` | Development AKS cluster name. |

No client secret, registry password, kubeconfig, or static token is stored in GitHub. Create federated identity credentials in Microsoft Entra for audience `api://AzureADTokenExchange`:

- Build identity subject: `repo:<OWNER>/<REPO>:ref:refs/heads/main`
- Deploy identity subject: `repo:<OWNER>/<REPO>:environment:dev`

Grant the build identity `AcrPush` scoped to the single ACR. Terraform enables managed Microsoft Entra integration and Azure RBAC authorization for Kubernetes and grants the deployment identity:

- `Azure Kubernetes Service Cluster User Role` at AKS resource scope, which permits retrieving user credentials but does not grant Kubernetes cluster-admin permissions.
- `Azure Kubernetes Service RBAC Writer` at AKS namespace scope `/namespaces/mt-saas`, for managing the namespaced workload resources used by the dev overlay.
- `Reader` at the ACR resource scope, for resolving the registry login server used to form the image name (no push permission).

The GitHub workflow gets normal user credentials with `az aks get-credentials` (no `--admin`) and runs `kubelogin convert-kubeconfig -l azurecli` to use its existing federated Azure CLI login for Kubernetes authentication. Configure Terraform's `aks_deployment_principal_object_id` to the Entra service principal **object ID** corresponding to `AZURE_DEPLOY_CLIENT_ID`, then apply the Terraform change using an authorized operator. If this optional variable is null, Terraform does not create the deployment role assignments.

The built-in Writer role is namespace-scoped and is not cluster administrator, but it is broader than an exact resource-type allow-list: it can access Secrets and create Pods using ServiceAccounts in that namespace. Treat the deployment identity as trusted for `mt-saas`, avoid placing higher-privilege credentials there, and review the Azure role definition for the target subscription/AKS version.

The namespace must already exist before the namespace-scope role assignment and deployment can be used. For a new cluster, first apply Terraform with `aks_deployment_principal_object_id = null`; an authorized platform operator bootstraps the namespace/workload; then set the service principal object ID and apply Terraform again to create the scoped role assignments. Existing M4 clusters with `mt-saas` already present can configure the object ID before their next Terraform apply. The dev overlay excludes the Namespace object so routine deployments do not require cluster-scoped namespace permissions. Azure role assignments can take several minutes to propagate.

Create or configure the GitHub Environment named `dev`. Environment protection rules/approvals can be applied there according to the repository's operating policy. A deployment job is restricted to workflow dispatch from `main`.

## Local validation and deployment

From the repository root, install the API test requirements and run the same core local checks:

```bash
python -m pip install -r application/api/requirements.txt
pytest -q
docker compose config
docker compose build
kubectl kustomize kubernetes/base
kubectl kustomize kubernetes/overlays/dev
bash -n scripts/*.sh
git diff --check
```

For a manual dev deployment, install `kubectl` and Kustomize 5.x, authenticate with Azure CLI, and set the target values:

```bash
az login
az aks get-credentials \
  --resource-group "<resource-group>" \
  --name "<aks-name>" \
  --overwrite-existing
kubelogin convert-kubeconfig -l azurecli
export ACR_LOGIN_SERVER="$(az acr show --name "<acr-name>" --query loginServer --output tsv)"
export IMAGE_TAG="<full-git-sha-of-an-image-published-to-acr>"
./scripts/deploy-dev.sh
```

Inspect `kubectl rollout status deployment/multi-tenant-saas-api -n mt-saas` and the release-identification command above after deployment.

## Limitations

- The dev cluster runs one replica. Although the rollout waits for readiness and allows one surge pod, it does not demonstrate production-grade zero downtime, canary analysis, or progressive traffic shifting.
- SQLite is stored in pod-local ephemeral storage; a replacement pod does not share the previous pod's database. This is inherited M4 behavior, not addressed by M7.
- Git SHA image tags are immutable by convention, but the workflow does not enforce registry tag immutability or sign/provenance-verify artifacts.
- The namespace-scoped AKS RBAC Writer role is broader than a strict object-kind allow-list, including access to Secrets and pod creation under ServiceAccounts in `mt-saas`; it is not cluster-admin but must still be treated as a trusted namespace-level identity.
- Azure OIDC, ACR publishing, and AKS deployment require GitHub/Azure configuration and were not executed by local validation.
- No deployment to pull-request code, automatic production promotion, canary, blue/green strategy, or M8+ observability tooling is included.
