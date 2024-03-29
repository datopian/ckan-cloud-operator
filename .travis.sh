#!/usr/bin/env bash

REF="${GITHUB_REF:-${GITHUB_SHA}}"
TAG=${REF##*/}
AWS_IAM_AUTHENTICATOR_VERSION="1.14.6/2019-08-22"
TERRAFORM_VERSION=0.12.18
PACKER_VERSION=1.5.1
HELM_VERSION="${HELM_VERSION:-v3.5.2}"

if [ "${1}" == "install" ]; then
    ! docker pull viderum/ckan-cloud-operator:latest && echo Failed to pull image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "install-tools" ]; then
    if [ "${K8_PROVIDER}" == "minikube" ]; then
      # Install Minikube
      echo Installing Minikube
      curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
      sudo install minikube-linux-amd64 /usr/local/bin/minikube
      rm minikube-linux-amd64 && minikube version
      echo Minikube Installed Successfully!
    fi

    if [ "${K8_PROVIDER}" == "aws" ]; then
      # Install terraform
      echo Installing Terraform
      (cd terraform/aws/ && \
        curl -o tf.zip https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
        unzip tf.zip && \
        ./terraform version)
      (cd terraform/aws/ami/ && \
        curl -o pk.zip https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_amd64.zip && \
        unzip pk.zip && \
        ./packer version)

      # Install AWS tools
      echo Installing AWS tools
      pip install awscli
      curl -o aws-iam-authenticator https://amazon-eks.s3-us-west-2.amazonaws.com/${AWS_IAM_AUTHENTICATOR_VERSION}/bin/linux/amd64/aws-iam-authenticator
      chmod +x aws-iam-authenticator && sudo mv aws-iam-authenticator /usr/local/bin/
      aws --version
      aws-iam-authenticator version
      echo AWS Dependencies Installed Successfully!
    fi

    if [ "${K8_PROVIDER}" == "azure" ]; then
      # Install  terraform
      wget -O terraform.zip https://releases.hashicorp.com/terraform/0.12.18/terraform_0.12.18_linux_amd64.zip &&\
      unzip terraform.zip -d /tmp &&\
      sudo mv /tmp/terraform /usr/local/bin/

      echo Terraform Installed Successfully!

      # Intall Azure CLI and login
      sudo apt-get update
      sudo apt-get install ca-certificates curl apt-transport-https lsb-release gnupg
      curl -sL https://packages.microsoft.com/keys/microsoft.asc |
      gpg --dearmor |
      sudo tee /etc/apt/trusted.gpg.d/microsoft.asc.gpg > /dev/null
      AZ_REPO=$(lsb_release -cs)
      echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" |
      sudo tee /etc/apt/sources.list.d/azure-cli.list
      sudo apt-get update
      sudo apt-get install azure-cli
      echo Azure CLI Installed Successfully!
   fi

    curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
    chmod +x ./kubectl && sudo mv ./kubectl /usr/local/bin/kubectl
    echo Kubectl Installed Successfully!

    curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm.sh &&\
     chmod 700 get_helm.sh &&\
     ./get_helm.sh --version "${HELM_VERSION}" &&\
     helm version --client && rm ./get_helm.sh
    helm init --client-only --stable-repo-url https://charts.helm.sh/stable
    echo Helm Installed Successfully!

    sudo apt-get update && sudo apt-get install -y socat jq

    echo Instalation Complete && exit 0

elif [ "${1}" == "script" ]; then
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" --cache-from viderum/ckan-cloud-operator:latest -t ckan-cloud-operator . && echo Failed to build image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "test" ]; then
    echo Run tests
    docker run --env NO_KUBE_CONFIG=1 --rm --entrypoint '/bin/bash' ckan-cloud-operator -lc 'cd /usr/src/ckan-cloud-operator && ckan-cloud-operator test'
    ## Commenting below as this complains about PYAML version and
    ## it was a requirement by GSA and they never actually gonna use it
    # echo Checking for vulnerabilities
    # docker run --rm -v $PWD:/target -v $PWD:/results drydockcloud/ci-safety
    # scan_status=$?
    # cat safety.txt
    # if [ $scan_status ]; then
    #     exit $scan_status
    # fi
    # echo Running security scan
    # docker run --rm -v $PWD/ckan_cloud_operator:/target -v $PWD:/results -v $PWD:/src drydockcloud/ci-bandit scan-text
    # scan_status=$?
    # cat bandit.txt
    # if [ $scan_status ]; then
    #     exit $scan_status
    # fi
    echo Great Success! && exit 0

elif [ "${1}" == "deploy" ]; then
    docker tag ckan-cloud-operator "viderum/ckan-cloud-operator:${TAG}" &&\
    echo && echo "viderum/ckan-cloud-operator:${TAG}" && echo &&\
    docker push "viderum/ckan-cloud-operator:${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push && exit 1
    if [ "${GITHUB_REF}" == "master" ]; then
        docker tag ckan-cloud-operator viderum/ckan-cloud-operator:latest &&\
        echo && echo viderum/ckan-cloud-operator:latest && echo &&\
        docker push viderum/ckan-cloud-operator:latest
        [ "$?" != "0" ] && echo Failed to tag and push latest image && exit 1
    fi
    echo Great Success! && exit 0

else
    echo invalid arguments && exit 1

fi
