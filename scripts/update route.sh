#!/usr/bin/env bash

export ARGS="${1}"

ckan-cloud-operator routers update ${ARGS}
