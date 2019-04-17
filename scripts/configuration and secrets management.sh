#!/usr/bin/env bash

export ACTION="${1}"
export ARGS="${2}"
! python3 -c "exit(0 if '${ACTION}' in [
    'get', 'set', 'list-configs', 'kubectl get secret'
] else 1)" && echo invalid ACTION && exit 1

if [ "${ACTION}" == "kubectl get secret" ]; then
	ckan-cloud-operator kubectl -- get secret ${ARGS}
else
	ckan-cloud-operator config "${ACTION}" ${ARGS}
fi
