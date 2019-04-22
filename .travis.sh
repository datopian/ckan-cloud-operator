#!/usr/bin/env bash

TAG="${TRAVIS_TAG:-${TRAVIS_COMMIT}}"

if [ "${1}" == "install" ]; then
    ! docker pull viderum/ckan-cloud-operator:latest && echo Failed to pull image && exit 1
    ! docker pull viderum/ckan-cloud-operator:jnlp-latest && echo Failed to pull jnlp image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "script" ]; then
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" --cache-from viderum/ckan-cloud-operator:latest -t ckan-cloud-operator . && echo Failed to build image && exit 1
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" --cache-from viderum/ckan-cloud-operator:jnlp-latest -t ckan-cloud-operator-jnlp -f Dockerfile.jenkins-jnlp . && echo Failed to build jnlp image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "deploy" ]; then
    docker tag ckan-cloud-operator "viderum/ckan-cloud-operator:${TAG}" &&\
    echo && echo "viderum/ckan-cloud-operator:${TAG}" && echo &&\
    docker push "viderum/ckan-cloud-operator:${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push && exit 1
    docker tag ckan-cloud-operator-jnlp "viderum/ckan-cloud-operator:jnlp-${TAG}" &&\
    echo && echo "viderum/ckan-cloud-operator:jnlp-${TAG}" && echo &&\
    docker push "viderum/ckan-cloud-operator:jnlp-${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push jnlp image && exit 1
    if [ "${TRAVIS_BRANCH}" == "master" ]; then
        docker tag ckan-cloud-operator viderum/ckan-cloud-operator:latest &&\
        echo && echo viderum/ckan-cloud-operator:latest && echo &&\
        docker push viderum/ckan-cloud-operator:latest
        [ "$?" != "0" ] && echo Failed to tag and push latest image && exit 1
        docker tag ckan-cloud-operator-jnlp viderum/ckan-cloud-operator:jnlp-latest &&\
        echo && echo viderum/ckan-cloud-operator:jnlp-latest && echo &&\
        docker push viderum/ckan-cloud-operator:jnlp-latest
        [ "$?" != "0" ] && echo Failed to tag and push jnlp latest image && exit 1
    fi
    if [ "${TRAVIS_TAG}" != "" ]; then
        export DEPLOY_JNLP_IMAGE="viderum/ckan-cloud-operator:jnlp-${TAG}"
        echo "Running Jenkins deploy jnlp job (JNLP_IMAGE=${DEPLOY_JNLP_IMAGE})"
        STATUS_CODE=$(curl -X POST "${JENKINS_JNLP_DEPLOY_URL}" --user "${JENKINS_USER}:${JENKINS_TOKEN}" \
                      --data-urlencode json='{"parameter":[{"name":"JNLP_IMAGE","value":"'${DEPLOY_JNLP_IMAGE}'"}]}' -s -o /dev/stderr -w "%{http_code}")
        echo "jenkins jnlp deploy job status code: ${STATUS_CODE}"
        [ "${STATUS_CODE}" != "200" ] && [ "${STATUS_CODE}" != "201" ] && echo Deploy failed && exit 1
    fi
    echo Great Success! && exit 0

else
    echo invalid arguments && exit 1

fi
