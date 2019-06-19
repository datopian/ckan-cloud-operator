#!/usr/bin/env bash

set -e

usage() {
    echo Manage CKAN Cloud operator environments
    echo
    echo Usage: ./ckan-cloud-operator-env.sh "<COMMAND> [ARGS..]"
    echo
    echo Available commands:
    echo
    echo "  pull <PATH_TO_KUBECONFIG_FILE>"
    echo "    Pulls the ckan-cloud-operator Docker image compatible with the cluster configured in the kubeconfig file"
    echo "    Required the kubectl binary to be available in your PATH"
    echo
    echo "  build"
    echo "    Build a ckan-cloud-operator image from current working directory and tag as latest image which"
    echo "    used by the installed environments"
    echo
    echo "  add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE> [--build | --dev] [DOCKER_RUN_ARGS..]"
    echo "    Add a ckan-cloud-operator executable at /usr/local/bin/ckan-cloud-operator-<ENVIRONMENT_NAME>"
    echo "    which runs using the ckan-cloud-operator Docker image"
    echo "    To use with Minikube set PATH_TO_KUBECONFIG_FILE to 'minikube'"
    echo "    If --build is set, a docker build will run on current working directory before each run"
    echo "    If --dev is set, the ckan-cloud-operator binary from local miniconda3 environment will be used instead of docker image"
    echo
    echo "  activate <ENVIRONMENT_NAME>"
    echo "    Installs a ckan-cloud-operator executable at /usr/local/bin/ckan-cloud-operator configured for the ENVIRONMENT_NAME"
}

check_namespace() {
    NAMESPACES=$(kubectl get namespaces)
    if [[ $NAMESPACES != *"ckan-cloud"* ]]
    then
        kubectl create namespace ckan-cloud
    fi
}

check_configmap() {
    NAMESPACES=$(kubectl get -n ckan-cloud configmaps)
    if [[ $NAMESPACES != *"operator-conf"* ]]
    then
        kubectl create -n ckan-cloud configmap operator-conf --from-literal=ckan-cloud-operator-image=viderum/ckan-cloud-operator:latest --from-literal=label-prefix=ckan-cloud
    fi
}

( [ "${1}" == "" ] || [ "${1}" == "-h" ] || [ "${1}" == "--help" ] ) && usage && exit 1

if [ "${1}" == "pull" ]; then
    if [ "${2}" == "latest" ]; then
        docker pull viderum/ckan-cloud-operator:latest >/dev/stderr &&\
        docker tag viderum/ckan-cloud-operator:latest ckan-cloud-operator &&\
        exit 0
    elif [ "${2}" != "" ]; then
        IMAGE=$(kubectl -n ckan-cloud get configmap operator-conf -o jsonpath={.data.ckan-cloud-operator-image})
        [ "${IMAGE}" == "" ] && echo Failed to get compatible operator version && exit 1
        docker pull "${IMAGE}" >/dev/stderr &&\
        docker tag "${IMAGE}" ckan-cloud-operator &&\
        exit 0
    fi
    echo Failed to pull latest ckan-cloud-operator image >/dev/stderr && exit 1

elif [ "${1}" == "build" ]; then
    docker build -t ckan-cloud-operator . >/dev/stderr && exit 0
    echo Failed to build ckan-cloud-operator image >/dev/stderr && exit 1

elif [ "${1}" == "add" ]; then
    ENVIRONMENT_NAME="${2}"
    KUBECONFIG_FILE="${3}"
    BUILD="${4}"
    RUN_ARGS="${@:5}"
    echo "#!/usr/bin/env bash" > "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}"
    [ "$?" != "0" ] && echo Failed to create executable, try running with sudo >/dev/stderr && exit 1
    if [ "${BUILD}" == "--dev" ]; then
        check_namespace
        check_configmap
        CMD="KUBECONFIG=\"${KUBECONFIG_FILE}\" ~/miniconda3/envs/ckan-cloud-operator/bin/ckan-cloud-operator \""'$@'"\""
    else
        if [ "${BUILD}" == "--build" ]; then
            CMD="docker build -t ckan-cloud-operator $(pwd) >/dev/stderr && "
            IMAGE="ckan-cloud-operator"
        else
            CMD=""
            if [ "${BUILD}" == "" ]; then
                IMAGE=$(docker run --entrypoint bash -v ${KUBECONFIG_FILE}:/.kube-config -e KUBECONFIG=/.kube-config viderum/ckan-cloud-operator:minimal-20190416 -c "kubectl -n ckan-cloud get configmap/operator-conf -ojsonpath={.data.ckan-cloud-operator-image}")
            else
                IMAGE="${BUILD}"
            fi
        fi
        if [ "${KUBECONFIG_FILE}" == "minikube" ]; then
            CMD="${CMD}docker run -v ${HOME}/.kube/config:/etc/ckan-cloud/.kube-config -v ${HOME}/.minikube:${HOME}/.minikube -e KUBE_CONTEXT=minikube ${RUN_ARGS} -it ${IMAGE} "'"$@"'
        else
            CMD="${CMD}docker run -v ${KUBECONFIG_FILE}:/etc/ckan-cloud/.kube-config ${RUN_ARGS} -it ${IMAGE} "'"$@"'
        fi
    fi
    echo "${CMD}" >> "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}" &&\
    chmod o+x "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}" &&\
    cp -f "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}" "/usr/local/bin/ckan-cloud-operator" &&\
    chmod o+x "/usr/local/bin/ckan-cloud-operator" &&\
    echo Great Success! >/dev/stderr && exit 0
    echo Failed to install >/dev/stderr && exit 1

elif [ "${1}" == "activate" ]; then
    ENVIRONMENT_NAME="${2}"
    cp -f "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}" "/usr/local/bin/ckan-cloud-operator" &&\
    chmod o+x "/usr/local/bin/ckan-cloud-operator" &&\
    echo Great Success! >/dev/stderr && exit 0
    echo Failed to create executable, try running with sudo >/dev/stderr && exit 1

else
    echo Invalid command "$@" >/dev/stderr && exit 1

fi
