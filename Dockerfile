FROM python:3.7.6-slim

WORKDIR /cco

RUN apt-get update
RUN apt-get install -y nano curl unzip sudo bash libpq-dev build-essential
ENV EDITOR nano

COPY . .
RUN K8_PROVIDER=aws TERRAFORM_VERSION=0.12.18 /cco/.travis.sh install-tools
RUN pip install -r requirements.txt
RUN pip install .

ENTRYPOINT [ "/bin/bash" ]
