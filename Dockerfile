FROM continuumio/miniconda3
RUN conda update -n base -c defaults conda
COPY docker-build.sh /usr/src/ckan-cloud-operator/
RUN /usr/src/ckan-cloud-operator/docker-build.sh
COPY environment.yaml /environment.yaml
RUN conda env create -f /environment.yaml
RUN echo conda activate ckan-cloud-operator >> ~/.bashrc &&\
    echo '[ -e /etc/ckan-cloud/.kube-config ] && export KUBECONFIG=/etc/ckan-cloud/.kube-config' >> ~/.bashrc &&\
    echo '! [ -z "${KUBE_CONTEXT}" ] && kubectl config use-context "${KUBE_CONTEXT}" >/dev/null 2>&1' >> ~/.bashrc &&\
    echo '! [ "$(ckan-cloud-operator config get --key=ckan-cloud-provider-cluster-main-provider-id --raw)" == "aws" ] && ckan-cloud-operator activate-gcloud-auth >/dev/null 2>&1' >> ~/.bashrc &&\
    echo 'ckan-cloud-operator db proxy port-forward --all-daemon "I know the risks" >/dev/null 2>&1' >> ~/.bashrc &&\
    echo 'while ! pg_isready -h localhost >/dev/null 2>&1; do sleep .1; done' >> ~/.bashrc
COPY ckan_cloud_operator /usr/src/ckan-cloud-operator/ckan_cloud_operator
COPY *.sh *.py /usr/src/ckan-cloud-operator/
RUN . /opt/conda/etc/profile.d/conda.sh && conda activate ckan-cloud-operator &&\
    cd /usr/src/ckan-cloud-operator && python3 -m pip install -e . &&\
    chmod +x /usr/src/ckan-cloud-operator/*.sh
COPY scripts /usr/src/ckan-cloud-operator/scripts
ENV CKAN_CLOUD_OPERATOR_SCRIPTS=/usr/src/ckan-cloud-operator/scripts
ENV EDITOR nano
ENTRYPOINT ["/usr/src/ckan-cloud-operator/entrypoint.sh"]

ARG CKAN_CLOUD_OPERATOR_IMAGE_TAG
RUN echo "${CKAN_CLOUD_OPERATOR_IMAGE_TAG}" > /etc/CKAN_CLOUD_OPERATOR_IMAGE_TAG
