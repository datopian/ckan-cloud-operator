#!/usr/bin/env bash

if [ "${1}" == "bash" ]; then
    if [ "${2}" == "" ]; then
        exec bash --init-file <(echo 'source ~/.bashrc; eval "$(_CKAN_CLOUD_OPERATOR_COMPLETE=source ckan-cloud-operator)"')
    else
        exec "$@"
    fi
else
    source ~/.bashrc
    ckan-cloud-operator "$@"
fi
