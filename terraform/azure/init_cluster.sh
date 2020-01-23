#!/bin/bash
set -e

if [ "$#" -ne 3 ] && [ "$#" -ne 4 ] && [ "$#" -ne 5 ]; then
    cat << USAGE

Initialize Azure CCO Cluster using terraform and ckan-cloud-operator

Usage:
${0} <azure-servce-principal-id> <azure-service-principal-secret> <azure-tenant-id> <azure-region[optional]> <cluster-name[optional]>

Note: it will overwrite your ~/.kube/config file

USAGE
    exit 1
fi

export TF_VAR_client_id="${1}"
export TF_VAR_client_secret="${2}"
export TF_VAR_tenant_id="${3}"
export TF_VAR_region="${4}"
export TF_VAR_cluster_name="${5}"

az login --service-principal -u $TF_VAR_client_id -p $TF_VAR_client_secret --tenant $TF_VAR_tenant_id

terraform init -input=false
terraform validate

terraform apply -input=false -auto-approve
terraform output cco-interactive-yaml > interactive.yaml
terraform output kube_config > ~/.kube/config

export CCO_INTERACTIVE_CI=interactive.yaml
cp terraform.tfstate ~/
ckan-cloud-operator cluster initialize --interactive --cluster-provider=azure
