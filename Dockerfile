FROM continuumio/miniconda3
RUN conda update -n base -c defaults conda
COPY docker-build.sh /usr/src/ckan-cloud-operator/
RUN /usr/src/ckan-cloud-operator/docker-build.sh
COPY environment.yaml /environment.yaml
COPY bashrc.inc /root/bashrc.inc
RUN conda env create -f /environment.yaml
RUN cat /root/bashrc.inc >> ~/.bashrc
COPY ckan_cloud_operator /usr/src/ckan-cloud-operator/ckan_cloud_operator
COPY tests /usr/src/ckan-cloud-operator/tests
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
