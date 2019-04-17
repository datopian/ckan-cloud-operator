#!/usr/bin/env bash

export DATAPACKAGE_PREFIX="${1}"
export NON_CKAN_INSTANCES="${2}"
[ -z "${DATAPACKAGE_PREFIX}" ] && echo invalid args && exit 1
echo DATAPACKAGE_PREFIX=$DATAPACKAGE_PREFIX
echo NON_CKAN_INSTANCES=$NON_CKAN_INSTANCES

rm -rf .checkpoints &&\
rm -rf data/$DATAPACKAGE_PREFIX &&\
python3 /home/jenkins/ckan-cloud-operator/ckan_cloud_operator/dataflows/resources.py &&\
python3 /home/jenkins/ckan-cloud-operator/ckan_cloud_operator/dataflows/ckan_images.py &&\
python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/ckan-cloud-prod/resources/datapackage.json'),
  printer(tablefmt='html', num_rows=9999)
).process()
" > resources.html
python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/ckan-cloud-prod/ckan_images/datapackage.json'),
  printer(resources=['dockerfiles'], tablefmt='html', num_rows=9999, fields=['gitlab_repo','name', 'url', 'instances','from','ckan_exts','ckanext-s3filestore'])
).process()
" > dockerfiles.html