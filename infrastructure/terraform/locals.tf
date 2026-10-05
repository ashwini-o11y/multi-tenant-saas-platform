locals {
  tags = {
    environment = var.environment
    project     = "multi-tenant-saas"
    managed_by  = "terraform"
  }
}
