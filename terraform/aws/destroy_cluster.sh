#!/bin/bash
set -e

if [ "$#" -ne 6 ]; then
    cat << USAGE

Destroy AWS CCO Cluster using terraform

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

./terraform destroy
