#!/usr/bin/env bash

# requires the node-management DaemonSet, see node-management/README.md. after updating the secret, redeploy the daemonset to apply the changes

export CMD
export KEY_NAME
export KEY

echo CMD=${CMD}
echo KEY_NAME=${KEY_NAME}
echo KEY=${KEY}

[ "${KEY_NAME}" == "" ] && echo missing KEY_NAME && exit 1

[ "$(python3 -c 'import os; print("yes" if all([c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_" for c in os.environ["KEY_NAME"]]) else "no")')" != "yes" ] \
    && echo invalid characters in KEY_NAME, only upper-case letters and underscore are permitted && exit 2

SECRET_NAME=ec2-user-authorized-keys
NAMESPACE=node-management

if [ "${CMD}" == "add" ]; then
    [ "${KEY}" == "" ] && echo KEY is missing && exit 3
    echo "Adding"
    ! ckan-cloud-operator config set --secret-name "${SECRET_NAME}" --namespace "${NAMESPACE}" "${KEY_NAME}" "${KEY}" && echo failed to update secret && exit 4
    echo key added successfully && ckan-cloud-operator config get --namespace "${NAMESPACE}" --secret-name "${SECRET_NAME}" && exit 0

elif [ "${CMD}" == "del" ]; then
    [ "${KEY}" != "" ] && echo KEY should be empty when deleting && exit 3
    echo "Deleting"
    ! ckan-cloud-operator config delete-key --secret-name "${SECRET_NAME}" --namespace "${NAMESPACE}" "${KEY_NAME}" && echo failed to delete key && exit 4
    echo key deleted successfull && ckan-cloud-operator config get --namespace "${NAMESPACE}" --secret-name "${SECRET_NAME}" && exit 0

elif [ "${CMD}" == "list" ]; then
    ckan-cloud-operator config get --namespace "${NAMESPACE}" --secret-name "${SECRET_NAME}" && exit 0

else
    echo invalid CMD && exit 4

fi
