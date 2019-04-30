#!/usr/bin/env bash

[ -z "${BASH_SCRIPT}" ] && exit 1
[ -z "${DEPLOYMENT_NAME}" ] && exit 2
[ -z "${NAMESPACE_NAME}" ] && exit 3

export BASH_SCRIPT
export DEPLOYMENT_NAME
export NAMESPACE_NAME

POD_NAME=$(python3 -c "
import os
from ckan_cloud_operator import kubectl
print(kubectl.get_deployment_pod_name(os.environ['DEPLOYMENT_NAME'], namespace=os.environ['NAMESPACE_NAME'], use_first_pod=True))
")

echo POD_NAME=$POD_NAME

TEMPFILE=`mktemp`

echo "${BASH_SCRIPT}" | tee $TEMPFILE

kubectl -n ${NAMESPACE_NAME} cp "${TEMPFILE}" "${POD_NAME}:${TEMPFILE}" &&\
kubectl -n ${NAMESPACE_NAME} exec "${POD_NAME}" bash "${TEMPFILE}"
