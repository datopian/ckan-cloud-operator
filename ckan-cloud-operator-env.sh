#!/usr/bin/env bash

help() {
    echo Manage CKAN Cloud operator environments
    echo
    echo Usage: ./ckan-cloud-operator-env.sh "<COMMAND> [ARGS..]"
    echo
    echo Available commands:
    echo
    echo "  pull"
    echo "    Pulls the latest ckan-cloud-operator Docker image which is used by the installed environments"
    echo
    echo "  build"
    echo "    Build a ckan-cloud-operator image from current working directory and tag as latest image which"
    echo "    used by the installed environments"
    echo
    echo "  add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE> [--build] [DOCKER_RUN_ARGS..]"
    echo "    Add a ckan-cloud-operator executable at /usr/local/bin/ckan-cloud-operator-<ENVIRONMENT_NAME>"
    echo "    which runs using the ckan-cloud-operator Docker image"
    echo "    To use with Minikube set PATH_TO_KUBECONFIG_FILE to 'minikube'"
    echo "    If --build is set, a docker build will run on current working directory before each run"
    echo
    echo "  activate <ENVIRONMENT_NAME>"
    echo "    Installs a ckan-cloud-operator executable at /usr/local/bin/ckan-cloud-operator configured for the ENVIRONMENT_NAME"
}

( [ "${1}" == "" ] || [ "${1}" == "-h" ] || [ "${1}" == "--help" ] ) && help && exit 1

if [ "${1}" == "pull" ]; then
    docker pull viderum/ckan-cloud-operator:latest >/dev/stderr && exit 0
    echo Failed to pull latest ckan-cloud-operator image >/dev/stderr && exit 1

elif [ "${1}" == "build" ]; then
    docker build -t viderum/ckan-cloud-operator:latest . >/dev/stderr && exit 0
    echo Failed to build ckan-cloud-operator image >/dev/stderr && exit 1

elif [ "${1}" == "add" ]; then
    ENVIRONMENT_NAME="${2}"
    KUBECONFIG_FILE="${3}"
    BUILD="${4}"
    RUN_ARGS="${@:5}"
    echo "#!/usr/bin/env bash" > "/usr/local/bin/ckan-cloud-operator-${ENVIRONMENT_NAME}"
    [ "$?" != "0" ] && echo Failed to create executable, try running with sudo >/dev/stderr && exit 1
    if [ "${BUILD}" == "--build" ]; then
        CMD="docker build -t viderum/ckan-cloud-operator:latest $(pwd) >/dev/stderr && "
    else
        CMD=""
    fi
    if [ "${KUBECONFIG_FILE}" == "minikube" ]; then
        CMD="${CMD}docker run -v ${HOME}/.kube/config:/etc/ckan-cloud/.kube-config -v ${HOME}/.minikube:${HOME}/.minikube -e KUBE_CONTEXT=minikube ${RUN_ARGS} -it viderum/ckan-cloud-operator:latest "'"$@"'
    else
        CMD="${CMD}docker run -v ${KUBECONFIG_FILE}:/etc/ckan-cloud/.kube-config ${RUN_ARGS} -it viderum/ckan-cloud-operator:latest "'"$@"'
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
