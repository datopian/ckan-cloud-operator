#!/bin/bash
set -e

if [ "$#" -ne 4 ] && [ "$#" -ne 5 ] && [ "$#" -ne 6 ]; then
    cat << USAGE

Initialize Azure CCO Cluster using terraform and ckan-cloud-operator

Usage:
${0} <azure-servce-principal-id> <azure-service-principal-secret> <azure-subscribtion-id> <azure-tenant-id> <azure-region[optional]> <cluster-name[optional]>

Note: it will overwrite your ~/.kube/config file

USAGE
    exit 1
fi

export TF_VAR_client_id="${1}"
export TF_VAR_client_secret="${2}"
export TF_VAR_subscribtion_id="${3}"
export TF_VAR_tenant_id="${4}"

if [ "${5}" ]; then
  export TF_VAR_region="${5}"
fi
if [ "${6}" ]; then
  export TF_VAR_cluster_name="${6}"
fi

mkdir -p ~/.kube

az login --service-principal -u $TF_VAR_client_id -p $TF_VAR_client_secret --tenant $TF_VAR_tenant_id

terraform init -input=false

echo 'Validating configuration...'
terraform validate

terraform apply -input=false -auto-approve
terraform output cco-interactive-yaml > interactive.yaml
terraform output kube_config > ~/.kube/config

cat ~/.kube/config

export CCO_INTERACTIVE_CI=interactive.yaml
cp terraform.tfstate ~/
ckan-cloud-operator cluster initialize --interactive --cluster-provider=azure
