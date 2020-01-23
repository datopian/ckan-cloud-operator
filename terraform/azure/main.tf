# AKS

variable "client_id" {}
variable "client_secret" {}

variable "location" {
  default  = "North Europe"
}

variable "cluster_name" {
   default = "terraform-cco"
}

variable "dns_zone_name" {
   default = "viderum.xyz"
}

resource "random_password" "cluster_name_suffix" {
  length = 4
  special = false
}

resource "azurerm_resource_group" "ckan_cloud_k8" {
  name     = "CkanCLoudk8Test"
  location = var.location
}

resource "azurerm_kubernetes_cluster" "ckan_cloud_k8" {
  name                = "${var.cluster_name}-${random_password.cluster_name_suffix.result}"
  location            = azurerm_resource_group.ckan_cloud_k8.location
  resource_group_name = azurerm_resource_group.ckan_cloud_k8.name
  dns_prefix          = "${var.cluster_name}-${random_password.cluster_name_suffix.result}-dns"

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

output "client_certificate" {
  value = azurerm_kubernetes_cluster.ckan_cloud_k8.kube_config.0.client_certificate
}

output "kube_config" {
  value = azurerm_kubernetes_cluster.ckan_cloud_k8.kube_config_raw
}


## AzureSQL

resource "random_password" "azuresql_password" {
  length = 16
  special = true
}

resource "azurerm_resource_group" "ckan_cloud_db" {
  name     = "CkanCLoudk8Test"
  location = var.location
}

resource "azurerm_postgresql_server" "ckan_cloud_db" {
  name                = "${var.cluster_name}-${random_password.cluster_name_suffix.result}-db"
  location            = azurerm_resource_group.ckan_cloud_db.location
  resource_group_name = azurerm_resource_group.ckan_cloud_db.name

  sku {
    name     = "B_Gen5_2"
    capacity = 2
    tier     = "Basic"
    family   = "Gen5"
  }

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
  resource_group_name = azurerm_resource_group.ckan_cloud_db.name
  server_name         = azurerm_postgresql_server.ckan_cloud_db.name
  charset             = "UTF8"
  collation           = "English_United States.1252"
}

resource "azurerm_postgresql_firewall_rule" "ckan_cloud_db" {
  name                = "firewallDB"
  resource_group_name = azurerm_resource_group.ckan_cloud_db.name
  server_name         = azurerm_postgresql_server.ckan_cloud_db.name
  start_ip_address    = "0.0.0.0"
  end_ip_address      = "0.0.0.0"
}

resource "azurerm_dns_zone" "ckan_cloud_dns_zone" {
  name                = var.dns_zone_name
  resource_group_name = azurerm_resource_group.ckan_cloud_k8.name
}


output "cco-interactive-yaml" {
  value = <<YAML
default:
  config:
    routers-config:
      env-id: p
      default-root-domain: "${var.dns_zone_name}"
      dns-provider: azure
    ckan-cloud-provider-cluster-azure:
      azure-rg: "${azurerm_resource_group.ckan_cloud_k8.name}"
      azure-default-location: "${azurerm_resource_group.ckan_cloud_k8.location}"
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
YAML
}
