#!/usr/bin/env bash

. /opt/conda/etc/profile.d/conda.sh && conda activate ckan-cloud-operator &&\
exec ckan-cloud-operator "$@"
