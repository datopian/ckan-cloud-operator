# CKAN Cloud Operator

CKAN Cloud operator manages, provisions and configures Ckan Cloud instances and related infrastructure.

## Install

Create secret `ckan-infra` under namespace `ckan-cloud` with the following values:

* GCLOUD_SQL_INSTANCE_NAME
* GCLOUD_SQL_PROJECT
* POSTGRES_HOST
* POSTGRES_PASSWORD
* SOLR_HTTP_ENDPOINT
* SOLR_NUM_SHARDS
* SOLR_REPLICATION_FACTOR
* DOCKER_REGISTRY_SERVER
* DOCKER_REGISTRY_USERNAME
* DOCKER_REGISTRY_PASSWORD
* DOCKER_REGISTRY_EMAIL

## Run using Docker

You will need the following details:

* Path to .kube-config file with permissions to the relevant Kubernetes cluster
* Path to Google Compute Cloud service account json with required permissions
* The Google service account email associated with the service account json

Run ckan-cloud-operator without arguments to get a help message:

```
docker run \
       -v /path/to/.kube-config:/etc/ckan-cloud/.kube-config \
       -v /path/to/glcoud-service-account.json:/etc/ckan-cloud/gcloud-service-account.json \
       -e GCLOUD_SERVICE_ACCOUNT_EMAIL= \
       -it viderum/ckan-cloud-operator
```

## Run locally

Ensure you have `kubectl` and `gcloud` binaries, authenticated to the relevant gcloud account / kubernetes cluster.

See the required system dependencies: [environment.yaml](environment.yaml)

You can [Install miniconda3](https://conda.io/miniconda.html), then create the environment using: `conda env create -f environment.yaml`

Activate the conda environment using `conda activate ckan-cloud-operator`

Run ckan-cloud-operator without arguments to get a help message:

```
ckan-cloud-operator
```

## Install custom resource definitions

Kubernetes custom resource definitions are used for management of the CKAN Cloud resources

Run the following command to ensure the crds are installed on the cluster

```
ckan-cloud-operator install-crds
```

