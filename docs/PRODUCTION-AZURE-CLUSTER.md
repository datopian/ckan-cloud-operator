# Creating a Production CKAN Cloud cluster using Azure Cloud Platform

## Prerequisites

* Logged in user (subscription) with admin privileges.
* Service Principal with default, "Contributor", role created
* Azure Resource Group Created
* Azure DNS Zone Created
* A CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

### Create Service Principal
```
az login
az account list
az account set -s <subscription id>
az ad sp create-for-rbac --name ckan-cloud
```

### Create Azure Resource Group

```
az group create --name CkanAzureGroup --location "East US"
```

### Create Azure DNS Zone

```
az network dns zone create -g CkanAzureGroup -n viderum.xyz
```

## Provision the cluster

### Terraform

In the CCO environment, go to the `terraform/azure` directory.

There you can find `main.tf`, which is a Terraform configuration file to provision a CCO cluster and some peripheral services.

It contains initializations for:
- an Azure Kubernetes cluster with a node-group of 3 nodes
- an AzureSQL Server and datase to serve as a centralized database for CKAN instance (Basic Tire)
- Postgresql firewall Rule to allow resource communicate inside the cluster

you could use this file as-is or tweak it based on your needs and requirements.

To apply the configuration, use `terraform apply`. You will need to set some input variables as environment variables (or create a `terraform.tfvars` file - see Terraform's docs for more info), like so:

```bash
export TF_VAR_client_id="..."               # Service Principal ID
export TF_VAR_client_secret="..."           # Service Principal Secret
export TF_VAR_tenant_id="..."               # Tenant ID
export TF_VAR_region="..."                  # Desired region.         Default: North Europe
export TF_VAR_cluster_name="..."            # Desired Cluster Name.   Default: terraform-cco

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
