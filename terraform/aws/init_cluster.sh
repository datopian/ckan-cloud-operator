#!/bin/bash
set -e

if [ "$#" -ne 6 ]; then
    cat << USAGE

Initialize AWS CCO Cluster using terraform and ckan-cloud-operator

Usage:
${0} <aws-access-key-id> <aws-secret-access-key> <aws-region> <vpc-id> <cluster-name> <external-domain>

Note: it will overwrite your ~/.kube/config and ~/.aws/credentials files

USAGE
    exit 1
fi

export TF_VAR_aws_access_key_id="${1}"
export TF_VAR_aws_secret_access_key="${2}"
export TF_VAR_region="${3}"
export TF_VAR_vpc_id="${4}"
export TF_VAR_cluster_name="${5}"
export TF_VAR_external_domain="${6}"

mkdir -p ~/.aws
cat > ~/.aws/credentials << CREDENTIALS
[default]
aws_access_key_id = ${TF_VAR_aws_access_key_id}
aws_secret_access_key = ${TF_VAR_aws_secret_access_key}
CREDENTIALS

./terraform init -input=false
./terraform validate

./terraform apply -input=false -auto-approve
./terraform output cco-interactive-yaml > interactive.yaml

export CCO_INTERACTIVE_CI=interactive.yaml
cp ./kubeconfig_terraform-cco ~/.kube/config
cp terraform.tfstate ~/
ckan-cloud-operator cluster initialize --cluster-provider=aws
