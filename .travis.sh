#!/usr/bin/env bash

TAG="${TRAVIS_TAG:-${TRAVIS_COMMIT}}"
AWS_IAM_AUTHENTICATOR_VERSION="1.14.6/2019-08-22"
TERRAFORM_VERSION=0.12.18
PACKER_VERSION=1.5.1
HELM_VERSION=v2.16.1

if [ "${1}" == "install" ]; then
    ! docker pull viderum/ckan-cloud-operator:latest && echo Failed to pull image && exit 1
    # ! docker pull viderum/ckan-cloud-operator:jnlp-latest && echo Failed to pull jnlp image && exit 1
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

    if [[ $K8_PROVIDER == custom-* ]]; then
      echo Installing ${K8_PROVIDER} from ${K8_PROVIDER_CUSTOM_DOWNLOAD_URL} &&\
      mkdir -p /usr/local/lib/cco/${K8_PROVIDER} &&\
      cd /usr/local/lib/cco/${K8_PROVIDER} &&\
      curl -Lo custom.tar.gz ${K8_PROVIDER_CUSTOM_DOWNLOAD_URL} &&\
      tar -xzvf custom.tar.gz && rm custom.tar.gz &&\
      mv `ls`/* ./ &&\
      source "/usr/local/lib/cco/${K8_PROVIDER}/install_tools_constants.sh"
      [ "$?" != "0" ] && exit 1
      ! bash "/usr/local/lib/cco/${K8_PROVIDER}/install_tools.sh" && exit 2
      echo ${K8_PROVIDER} Dependencies Installed Successfully!
    fi

    curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
    chmod +x ./kubectl && sudo mv ./kubectl /usr/local/bin/kubectl
    echo Kubectl Installed Successfully!

    curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm.sh &&\
     chmod 700 get_helm.sh &&\
     ./get_helm.sh --version "${HELM_VERSION}" &&\
     helm version --client && rm ./get_helm.sh
    echo Helm Installed Successfully!

    sudo apt-get update && sudo apt-get install -y socat jq

    echo Instalation Complete && exit 0

elif [ "${1}" == "script" ]; then
    ! docker build --cache-from viderum/ckan-cloud-operator:latest \
                   -t ckan-cloud-operator \
                   . && echo Failed to build image && exit 1
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" \
                   --cache-from viderum/ckan-cloud-operator:jnlp-latest \
                   -t ckan-cloud-operator-jnlp \
                   -f Dockerfile.jenkins-jnlp \
                   . && echo Failed to build jnlp image && exit 1
    ! docker build --build-arg "K8_PROVIDER=minikube" \
                   --cache-from viderum/ckan-cloud-operator:minikube-latest \
                   -t ckan-cloud-operator-minikube \
                   . && echo Failed to build minikube image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "test" ]; then
    echo Run tests
    docker run --env NO_KUBE_CONFIG=1 --rm --entrypoint '/bin/bash' ckan-cloud-operator -lc 'cd /usr/src/ckan-cloud-operator && ckan-cloud-operator test'
    echo Running security scan
    docker run --rm -v $PWD/ckan_cloud_operator:/target -v $PWD:/results -v $PWD:/src drydockcloud/ci-bandit scan-text
    scan_status=$?
    cat bandit.txt
    if [ $scan_status ]; then
        exit $scan_status
    fi
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

    docker tag ckan-cloud-operator-minikube "viderum/ckan-cloud-operator:minikube-${TAG}" &&\
    echo && echo "viderum/ckan-cloud-operator:minikube-${TAG}" && echo &&\
    docker push "viderum/ckan-cloud-operator:minikube-${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push minikube image && exit 1

    if [ "${TRAVIS_BRANCH}" == "master" ]; then
        docker tag ckan-cloud-operator viderum/ckan-cloud-operator:latest &&\
        echo && echo viderum/ckan-cloud-operator:latest && echo &&\
        docker push viderum/ckan-cloud-operator:latest
        [ "$?" != "0" ] && echo Failed to tag and push latest image && exit 1

        docker tag ckan-cloud-operator-jnlp viderum/ckan-cloud-operator:jnlp-latest &&\
        echo && echo viderum/ckan-cloud-operator:jnlp-latest && echo &&\
        docker push viderum/ckan-cloud-operator:jnlp-latest
        [ "$?" != "0" ] && echo Failed to tag and push jnlp latest image && exit 1

        docker tag ckan-cloud-operator-minikube viderum/ckan-cloud-operator:minikube-latest &&\
        echo && echo viderum/ckan-cloud-operator:minikube-latest && echo &&\
        docker push viderum/ckan-cloud-operator:minikube-latest
        [ "$?" != "0" ] && echo Failed to tag and push minikube latest image && exit 1
    fi

    if [ "${TRAVIS_TAG}" != "" ]; then
        export DEPLOY_JNLP_IMAGE="viderum/ckan-cloud-operator:jnlp-${TAG}"
        echo "Running Jenkins deploy jnlp job (JNLP_IMAGE=${DEPLOY_JNLP_IMAGE})"
        STATUS_CODE=$(curl -X POST "${JENKINS_JNLP_DEPLOY_URL}" --user "${JENKINS_USER}:${JENKINS_TOKEN}" --data "JNLP_IMAGE=${DEPLOY_JNLP_IMAGE}" -s -o /dev/stderr -w "%{http_code}")
        echo "jenkins jnlp deploy job status code: ${STATUS_CODE}"
        [ "${STATUS_CODE}" != "200" ] && [ "${STATUS_CODE}" != "201" ] && echo Deploy failed && exit 1
    fi

    echo Great Success! && exit 0

else
    echo invalid arguments && exit 1

fi
