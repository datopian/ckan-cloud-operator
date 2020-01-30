## Variables

variable "client_id" {}
variable "client_secret" {}
variable "tenant_id" {}
variable "subscribtion_id" {}

variable "location" {
  default  = "North Europe"
}

variable "cluster_name" {
   default = "terraform-cco"
}

variable "rg_name" {
   default = "terraformccotest"
}

variable "create_resoource_group" {
   default = false
}

variable "dns_provider" {
  default = "azure"
}

variable "dns_zone_name" {
   default = "viderum.xyz"
}

variable "create_dns_zone" {
  default = false
}

resource "random_string" "cluster_name_suffix" {
  length = 4
  special = false
}


## Resource Groups

# export TF_VAR_create_resoource_group=true to create resource group
resource "azurerm_resource_group" "ckan_cloud_operator" {
  count = var.create_resoource_group ? 1 : 0

  name     = var.rg_name
  location = var.location
}


## AKS

resource "azurerm_kubernetes_cluster" "ckan_cloud_k8" {
  name                = "${var.cluster_name}-${random_string.cluster_name_suffix.result}"
  location            = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].location : var.location
  resource_group_name = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].name : var.rg_name
  dns_prefix          = "${var.cluster_name}-${random_string.cluster_name_suffix.result}-dns"

  default_node_pool {
    name       = "default"
    node_count = 3
    vm_size    = "Standard_D2_v2"
  }

  service_principal {
    client_id     = var.client_id
    client_secret = var.client_secret
  }
}


## AzureSQL

resource "random_password" "azuresql_password" {
  length = 16
  special = true
}

resource "azurerm_postgresql_server" "ckan_cloud_db" {
  name                = "cco-terraform-${random_string.cluster_name_suffix.result}-db"
  location            = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].location : var.location
  resource_group_name = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].name : var.rg_name

  storage_profile {
    storage_mb            = 5120
    backup_retention_days = 7
    geo_redundant_backup  = "Disabled"
  }

  administrator_login          = "ckan_cloud"
  administrator_login_password = random_password.azuresql_password.result
  version                      = "9.6"
  ssl_enforcement              = "Disabled"
}

resource "azurerm_postgresql_database" "ckan_cloud_db" {
  name                = "ckan_cloud"
  resource_group_name = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].name : var.rg_name
  server_name         = azurerm_postgresql_server.ckan_cloud_db.name
  charset             = "UTF8"
  collation           = "English_United States.1252"
}

resource "azurerm_postgresql_firewall_rule" "ckan_cloud_db" {
  name                = "firewallDB"
  resource_group_name = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].name : var.rg_name
  server_name         = azurerm_postgresql_server.ckan_cloud_db.name
  start_ip_address    = "0.0.0.0"
  end_ip_address      = "0.0.0.0"
}


## DNS

# export TF_VAR_create_dns_zone=true to create DNS zone
resource "azurerm_dns_zone" "ckan_cloud_dns_zone" {
  count = var.create_dns_zone ? 1 : 0

  name                = var.dns_zone_name
  resource_group_name = var.create_resoource_group ? azurerm_resource_group.ckan_cloud_operator[0].name : var.rg_name
}


## Outputs

output "client_certificate" {
  value = azurerm_kubernetes_cluster.ckan_cloud_k8.kube_config.0.client_certificate
}

output "kube_config" {
  value = azurerm_kubernetes_cluster.ckan_cloud_k8.kube_config_raw
}

output "cco-interactive-yaml" {
  value = <<YAML
default:
  config:
    routers-config:
      env-id: p
      default-root-domain: "${var.dns_zone_name}"
      dns-provider: "${var.dns_provider}"
    ckan-cloud-provider-cluster-azure:
      azure-rg: "${var.rg_name}"
      azure-default-location: "${azurerm_kubernetes_cluster.ckan_cloud_k8.location}"
      azure-cluster-name: "${azurerm_kubernetes_cluster.ckan_cloud_k8.name}"
  secrets:
    solr-config:
      self-hosted: y
      num-shards: "1"
      replication-factor: "3"
    ckan-storage-config:
      default-storage-bucket: ckan
    ckan-cloud-provider-db-azuresql-credentials:
      azuresql-instance-name: "${azurerm_postgresql_server.ckan_cloud_db.name}"
      azuresql-host: "${azurerm_postgresql_server.ckan_cloud_db.name}.postgres.database.azure.com"
      admin-user: "${azurerm_postgresql_server.ckan_cloud_db.administrator_login}@${azurerm_postgresql_server.ckan_cloud_db.name}"
      admin-password: "${azurerm_postgresql_server.ckan_cloud_db.administrator_login_password}"
    ckan-cloud-provider-cluster-azure:
      azure-client-id: "${var.client_id}"
      azure-client-secret: "${var.client_secret}"
      azure-tenant-id: "${var.tenant_id}"
      azure-subscribtion-id: "${var.subscribtion_id}"
YAML
}
