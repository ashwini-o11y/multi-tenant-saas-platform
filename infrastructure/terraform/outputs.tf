output "resource_group_name" {
  description = "Resource group containing the M4 platform."
  value       = azurerm_resource_group.main.name
}

output "acr_name" {
  description = "Azure Container Registry name."
  value       = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "ACR login server used to tag and push the API image."
  value       = azurerm_container_registry.main.login_server
}

output "aks_cluster_name" {
  description = "AKS cluster name used by az aks get-credentials."
  value       = azurerm_kubernetes_cluster.main.name
}

output "aks_kubelet_identity_object_id" {
  description = "Kubelet managed identity object ID granted AcrPull on this registry."
  value       = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}

output "vnet_name" {
  description = "Virtual network name."
  value       = azurerm_virtual_network.main.name
}

output "aks_subnet_name" {
  description = "AKS subnet name."
  value       = azurerm_subnet.aks.name
}

output "api_image" {
  description = "API image reference for the separately managed Kubernetes deployment."
  value       = var.api_image
}
