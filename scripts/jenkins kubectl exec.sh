#!/usr/bin/env bash

[ -z "${BASH_SCRIPT}" ] && exit 1

JENKINS_POD_NAME=$(python3 -c "
from ckan_cloud_operator import kubectl
print(kubectl.get_deployment_pod_name('jenkins', namespace='jenkins', use_first_pod=True))
")

echo JENKINS_POD_NAME=$JENKINS_POD_NAME

TEMPFILE=`mktemp`

echo "${BASH_SCRIPT}" | tee $TEMPFILE

kubectl -n jenkins cp "${TEMPFILE}" "${JENKINS_POD_NAME}:${TEMPFILE}" &&\
kubectl -n jenkins exec "${JENKINS_POD_NAME}" bash "${TEMPFILE}"
