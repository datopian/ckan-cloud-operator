#!/usr/bin/env bash

if [ "${1}" == "bash" ]; then
    exec bash --init-file <(echo 'source ~/.bashrc; eval "$(_CKAN_CLOUD_OPERATOR_COMPLETE=source ckan-cloud-operator)"')
else
    source ~/.bashrc
    ckan-cloud-operator "$@"
fi
