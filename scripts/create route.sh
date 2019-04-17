#!/usr/bin/env bash

export CREATE_CMD="${1}"
export EXTRA_ARGS="${2}"
! python3 -c "exit(0 if '${CREATE_CMD}' in [
    'create-deis-instance-subdomain-route', 'create-backend-url-subdomain-route'
] else 1)" && echo invalid CREATE_CMD && exit 1

ckan-cloud-operator routers $CREATE_CMD ${EXTRA_ARGS}
