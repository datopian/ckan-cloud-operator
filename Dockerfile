FROM continuumio/miniconda3:4.5.11
RUN conda update -n base -c defaults conda
COPY environment.yaml /environment.yaml
RUN conda env create -f /environment.yaml
RUN apt-get update && apt-get install -y lsb-release gnupg
RUN export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" && \
    echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update -y && apt-get install google-cloud-sdk -y &&\
    apt-get update -y && apt-get install -y kubectl
RUN echo conda activate ckan-cloud-operator >> ~/.bashrc &&\
    echo '[ -e /etc/ckan-cloud/.kube-config ] && export KUBECONFIG=/etc/ckan-cloud/.kube-config' >> ~/.bashrc &&\
    echo '[ -e /etc/ckan-cloud/gcloud-service-account.json ] && ! [ -z "${GCLOUD_SERVICE_ACCOUNT_EMAIL}" ] && gcloud --project="${GCLOUD_AUTH_PROJECT}" auth activate-service-account "${GCLOUD_SERVICE_ACCOUNT_EMAIL}" --key-file=/etc/ckan-cloud/gcloud-service-account.json' >> ~/.bashrc &&\
    mkdir /usr/src/ckan-cloud-operator
COPY ckan_cloud_operator /usr/src/ckan-cloud-operator/ckan_cloud_operator
COPY entrypoint.sh LICENSE MANIFEST.in README.md setup.py VERSION.txt /usr/src/ckan-cloud-operator/
RUN . /opt/conda/etc/profile.d/conda.sh && conda activate ckan-cloud-operator &&\
    cd /usr/src/ckan-cloud-operator && python3 -m pip install -e .
ENTRYPOINT ["/usr/src/ckan-cloud-operator/entrypoint.sh"]
