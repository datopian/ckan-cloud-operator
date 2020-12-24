#!/usr/bin/env bash

date +%Y-%m-%d\ %H:%M | tee /etc/ckan-cloud-operator-build-info
hostname | tee -a /etc/ckan-cloud-operator-build-info
HELM_VERSION="${HELM_VERSION:-v2.16.1}"
echo $HELM_VERSION
(
  echo == system dependencies, gcloud-sdk &&\
  apt-get update && apt-get install -y gnupg bash-completion build-essential jq python-pip &&\
  /usr/bin/pip2 install pyopenssl &&\
  echo "deb http://packages.cloud.google.com/apt cloud-sdk-stretch main" >> /etc/apt/sources.list.d/google-cloud-sdk.list && \
  curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
  apt-get update -y && apt-get install -y google-cloud-sdk kubectl postgresql nano dnsutils &&\
  echo == helm, tiller &&\
  wget -q https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz &&\
  tar -xzf helm-$HELM_VERSION-linux-amd64.tar.gz &&\
  mv linux-amd64/helm /usr/local/bin/ && mv linux-amd64/tiller /usr/local/bin/ &&\
  chmod +x /usr/local/bin/helm /usr/local/bin/tiller && rm -rf linux-amd64 &&\
  echo == minio client &&\
  wget -q https://dl.minio.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc &&\
  chmod +x /usr/local/bin/mc
) >/dev/stdout 2>&1 | tee -a /etc/ckan-cloud-operator-build-info

[ "$?" != "0" ] && exit 1
echo Great Success! && exit 0
