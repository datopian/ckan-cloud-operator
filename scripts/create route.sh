#!/usr/bin/env bash

echo CREATE_CMD="${CREATE_CMD}"
echo EXTRA_ARGS="${EXTRA_ARGS}"

! python3 -c "exit(0 if '${CREATE_CMD}' in [
    'create-deis-instance-subdomain-route', 'create-backend-url-subdomain-route', 'create-ckan-instance-subdomain-route'
] else 1)" && echo invalid CREATE_CMD && exit 1

ckan-cloud-operator routers $CREATE_CMD ${EXTRA_ARGS}
