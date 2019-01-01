#!/usr/bin/env bash

VERSION_LABEL="${1}"

[ "${VERSION_LABEL}" == "" ] \
    && echo Missing version label \
    && echo current VERSION.txt = $(cat VERSION.txt) \
    && exit 1

echo "${VERSION_LABEL}" > VERSION.txt &&\
python setup.py sdist &&\
twine upload dist/ckan_cloud_operator-${VERSION_LABEL}.tar.gz &&\
docker build -t viderum/ckan-cloud-operator:v${VERSION_LABEL} . &&\
docker push viderum/ckan-cloud-operator:v${VERSION_LABEL} &&\
docker tag viderum/ckan-cloud-operator:v${VERSION_LABEL} viderum/ckan-cloud-operator:latest &&\
docker push viderum/ckan-cloud-operator:latest &&\
echo viderum/ckan-cloud-operator:v${VERSION_LABEL} &&\
echo viderum/ckan-cloud-operator:latest &&\
echo Great Success &&\
exit 0

exit 1
