#!/usr/bin/env bash
USER="${1}"
TOKEN="${2}"
URL="${3}"
DATA="${4}"

( [ -z "${USER}" ] || [ -z "${TOKEN}" ] || [ -z "${URL}" ] ) &&\
    echo ./jenkins-curl.sh '<JENKINS_USER> <JENKINS_TOKEN> <URL> [POST_JSON_DATA]' &&\
    exit 1

TEMPFILE=`mktemp`

STATUS_CODE=$(
    curl -X POST "${URL}" --user "${USER}:${TOKEN}" \
         --data-urlencode "json=${DATA}" -s -o "${TEMPFILE}" -w "%{http_code}"
)

cat "${TEMPFILE}" && rm "${TEMPFILE}"
[ "$?" != "0" ] && exit 1

[ "${STATUS_CODE}" != "200" ] && [ "${STATUS_CODE}" != "201" ] && [ "${STATUS_CODE}" != "302" ] && echo ERROR! Failed with status code: ${STATUS_CODE} >/dev/stderr && exit 1

exit 0
