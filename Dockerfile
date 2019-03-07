FROM continuumio/miniconda3:4.5.11
RUN conda update -n base -c defaults conda
RUN apt-get update && apt-get install -y gnupg bash-completion
RUN echo "deb http://packages.cloud.google.com/apt cloud-sdk-stretch main" >> /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update -y && apt-get install -y google-cloud-sdk kubectl postgresql nano
COPY environment.yaml /environment.yaml
RUN conda env create -f /environment.yaml
RUN echo conda activate ckan-cloud-operator >> ~/.bashrc &&\
    echo '[ -e /etc/ckan-cloud/.kube-config ] && export KUBECONFIG=/etc/ckan-cloud/.kube-config' >> ~/.bashrc &&\
    echo '! [ -z "${KUBE_CONTEXT}" ] && kubectl config use-context "${KUBE_CONTEXT}" >/dev/null 2>&1' >> ~/.bashrc &&\
    echo 'ckan-cloud-operator activate-gcloud-auth >/dev/null 2>&1' >> ~/.bashrc &&\
    echo '( ckan-cloud-operator db proxy port-forward & ) >/dev/null 2>&1' >> ~/.bashrc &&\
    echo 'while ! pg_isready -h localhost >/dev/null 2>&1; do sleep .1; done' >> ~/.bashrc &&\
    mkdir /usr/src/ckan-cloud-operator
COPY ckan_cloud_operator /usr/src/ckan-cloud-operator/ckan_cloud_operator
COPY entrypoint.sh setup.py /usr/src/ckan-cloud-operator/
RUN . /opt/conda/etc/profile.d/conda.sh && conda activate ckan-cloud-operator &&\
    cd /usr/src/ckan-cloud-operator && python3 -m pip install -e .
ENV EDITOR nano
ENTRYPOINT ["/usr/src/ckan-cloud-operator/entrypoint.sh"]
