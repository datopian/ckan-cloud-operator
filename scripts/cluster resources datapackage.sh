#!/usr/bin/env bash

export DATAPACKAGE_PREFIX="${1}"
export NON_CKAN_INSTANCES="${2}"
export SKIP_CKAN_IMAGES="${3}"
[ -z "${DATAPACKAGE_PREFIX}" ] && echo invalid args && exit 1
echo DATAPACKAGE_PREFIX=$DATAPACKAGE_PREFIX
echo NON_CKAN_INSTANCES=$NON_CKAN_INSTANCES

rm -rf .checkpoints &&\
rm -rf data/$DATAPACKAGE_PREFIX &&\
python3 /home/jenkins/ckan-cloud-operator/ckan_cloud_operator/dataflows/resources.py
[ "$?" != "0" ] && exit 1
! python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/${DATAPACKAGE_PREFIX}/resources/datapackage.json'),
  printer(tablefmt='html', num_rows=9999)
).process()
" > resources.html && exit 1

if [ "${SKIP_CKAN_IMAGES}" != "yes" ]; then
  ! python3 /home/jenkins/ckan-cloud-operator/ckan_cloud_operator/dataflows/ckan_images.py && exit 1
  ! python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/${DATAPACKAGE_PREFIX}/ckan_images/datapackage.json'),
  printer(resources=['dockerfiles'], tablefmt='html', num_rows=9999, fields=['gitlab_repo','name', 'url', 'instances','from','ckan_exts','ckanext-s3filestore'])
).process()
" > dockerfiles.html && exit 1
fi
