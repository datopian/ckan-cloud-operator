#!/usr/bin/env bash

export SOLR_URL
export SOLR_AUTH="$(echo ${SOLR_USER}:${SOLR_PASSWORD} | base64)"
bash /templater.sh /default.conf.template > /etc/nginx/conf.d/default.conf
echo Proxying requests from port 8983 to ${SOLR_URL} ${SOLR_USER} ${SOLR_PASSWORD}
cd /etc/nginx
exec nginx -g "daemon off;"
