# Creating a Production CKAN Cloud cluster using Azure Cloud Platform

## Prerequisites

* Logged in user (subscription) with admin privileges.
* Service Principal with default, "Contributor", role created
* Azure Resource Group Created
  * Or Service Principal should have permissions to create one
* Azure DNS Zone Created
  * Or Service Principal should have permissions to create one
* A CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

### Create Service Principal

```
az login
az account list
az account set -s <subscription id>
az ad sp create-for-rbac --role="Contributor" --scopes="/subscriptions/<subscription id>"
```

### Configure Azure Resource Group

You might already have [Azure Resource Group](https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/overview#resource-groups) created that you want to use for deploying cluster. Use `TF_VAR_rg_name` environment variable to set it

```
export TF_VAR_rg_name=MyResourceGroup
```

Alternatively you can leave that for Terraform to take care (You will need sufficient permissions for that). To do so export following environment variables:

```
export TF_VAR_rg_name=MyResourceGroup
export TF_VAR_create_resoource_group=true
```

### Configure Azure DNS Zone

Normally we expect [Azure DNS Zone](https://docs.microsoft.com/en-us/azure/dns/dns-zones-records) to be created in case you are going to use Azure as a DNS provider. Use `TF_VAR_dns_zone_name` environment variable to set it

```
export TF_VAR_dns_zone_name=ckan.xyz
```

Alternatively you can leave that for Terraform to take care (You will need sufficient permissions for that). To do so export following environment variables:

```
export TF_VAR_dns_zone_name=ckan.xyz
export TF_VAR_dns_provider=azure
export TF_VAR_create_dns_zone=true
```

## Provision the cluster

### Terraform

In the CCO environment, go to the `terraform/azure` directory.

There you can find `main.tf`, which is a Terraform configuration file to provision a CCO cluster and some peripheral services.

It contains initializations for:
- an Azure Kubernetes cluster with a node-group of 3 nodes
- an AzureSQL Server and datase to serve as a centralized database for CKAN instance (Basic Tire)
- Postgresql firewall Rule to allow resource communicate inside the cluster
- Storage Account for using ABS as a ckan storage

you could use this file as-is or tweak it based on your needs and requirements.

To apply the configuration, use `terraform apply`. You will need to set some input variables as environment variables (or create a `terraform.tfvars` file - see Terraform's docs for more info), like so:

```bash
export TF_VAR_client_id="..."               # Service Principal ID
export TF_VAR_client_secret="..."           # Service Principal Secret
export TF_VAR_subscribtion_id="..."         # Subscribtion ID
export TF_VAR_tenant_id="..."               # Tenant ID
export TF_VAR_location="..."                # location                          [Optional] Default: North Europe
export TF_VAR_cluster_name="..."            # Cluster Name                      [Optional] Default: terraform-cco
export TF_VAR_rg_name="..."                 # Resource Group Name               [Optional] Default: TerraformCCOTest
export TF_VAR_create_resoource_group="..."  # Allow Terraform create RG         [Optional] Default: false
export TF_VAR_dns_provider="..."            # DNS Provider                      [Optional] Default: azure
export TF_VAR_dns_zone_name="..."           # Azure DNS Zone name               [Optional] Default: viderum.xyz
export TF_VAR_create_dns_zone="..."         # Allow Terraform create DNS Zone   [Optional] Default: false

# Private docker Registry
export TF_VAR_private_registry="..."                  # Enable private container registry [Optional] Default: n
export TF_VAR_docker_server="..."                     # Container registry server name    [Required if private_registry=y]
export TF_VAR_docker_username="..."                   # Container registry username       [Required if private_registry=y]
export TF_VAR_docker_password="..."                   # Container registry password       [Required if private_registry=y]
export TF_VAR_docker_email="..."                      # Container registry user email     [Required if private_registry=y]
export TF_VAR_docker_image_pull_secret_name="..."     # Secret name for storing registry secrets (Same as imagePullSecret) [Optional] Default: container-registry
terraform apply
```

Once Terraform completes, it will generate a CCO initialization parameter object.
You can save it to a file like so:

```
terraform output cco-interactive-yaml > interactive.yaml
```

A `kubectl` configuration is also created in the process, and it will be saved in the local directory as `kubeconfig_<cluster-name>`.
You should copy it to `~/.kube/config` or set the `KUBECONFIG` environment variable to point to it.

```bash
export KUBECONFG=kubeconfig_<cluster-name>
```

### CCO Provision Cluster

Once Terraform finishes the cluser setup, we can use CCO to initialize the cluster itself.

CCO initialize will:
- Create all necessary K8S objects and configurations
- Run required services on the cluster (DB proxy, EFS provisioner, SOLR Cloud etc.) and initialize them properly.

For an unattended initialization, using the outputs of `terraform apply`, run:

```bash
export CCO_INTERACTIVE_CI=interactive.yaml
ckan-cloud-operator cluster initialize --interactive --cluster-provider=azure
```

You can also run the same without setting the `CCO_INTERACTIVE_CI` environment variable for an interactive initialization session.
