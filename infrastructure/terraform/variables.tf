variable "location" {
  description = "Azure region for the resource group and its resources."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the Azure resource group."
  type        = string
  default     = "rg-mt-saas-dev"
}

variable "acr_name" {
  description = "Globally unique ACR name containing 5-50 lowercase letters and numbers."
  type        = string
  default     = "acrmtsaasdev001"

  validation {
    condition     = can(regex("^[a-z0-9]{5,50}$", var.acr_name))
    error_message = "acr_name must contain 5-50 lowercase letters or numbers."
  }
}

variable "cluster_name" {
  description = "Name of the AKS cluster."
  type        = string
  default     = "aks-mt-saas-dev"
}

variable "vnet_address_space" {
  description = "CIDR address space for the virtual network."
  type        = string
  default     = "10.20.0.0/16"
}

variable "aks_subnet_address_prefix" {
  description = "CIDR address prefix for the AKS subnet; it must be inside the VNet."
  type        = string
  default     = "10.20.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.aks_subnet_address_prefix))
    error_message = "aks_subnet_address_prefix must be a valid IPv4 CIDR."
  }
}

variable "node_count" {
  description = "Number of nodes in the AKS system node pool."
  type        = number
  default     = 1

  validation {
    condition     = var.node_count >= 1 && var.node_count <= 10
    error_message = "node_count must be between 1 and 10 for this development configuration."
  }
}

variable "node_vm_size" {
  description = "Azure VM size for each AKS system node."
  type        = string
  default     = "Standard_D2s_v3"
}

variable "kubernetes_version" {
  description = "Optional AKS Kubernetes version. Null lets Azure select its current default."
  type        = string
  default     = null
  nullable    = true
}

variable "environment" {
  description = "Environment label applied to Azure resource tags."
  type        = string
  default     = "dev"
}

variable "api_image" {
  description = "Full API image reference for the separate Kubernetes deployment workflow."
  type        = string
  default     = "REPLACE_WITH_ACR_LOGIN_SERVER/multi-tenant-saas/api:REPLACE_WITH_GIT_SHA"
}
