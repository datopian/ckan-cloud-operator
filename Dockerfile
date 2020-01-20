FROM python:3.7.6-slim

WORKDIR /cco

RUN apt-get update 
RUN apt-get install -y nano curl unzip sudo bash libpq-dev build-essential 
ENV EDITOR nano

COPY . .
ARG K8_PROVIDER=aws
ENV K8_PROVIDER=$K8_PROVIDER
ARG K8_PROVIDER_CUSTOM_DOWNLOAD_URL=""
RUN /cco/.travis.sh install-tools
RUN pip install .

ENTRYPOINT [ "/bin/bash" ]