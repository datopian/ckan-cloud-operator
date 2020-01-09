# Creating a Production CKAN Cloud cluster using Azure Cloud Platform

## Create an AKS cluster
TODO

## Create SQL instance
TODO

## Create Service Principal
```
az login
az account list
az account set -s <subscription id>
az ad sp create-for-rbac --name ckan-cloud
```

## Install the management server

The management server is an optional but recommended component which provides management services for the cluster.

Follow [this guide](https://github.com/ViderumGlobal/ckan-cloud-cluster/blob/master/docs/MANAGEMENT.md) to create the server and deploy Rancher and Jenkins on it.

## Import the cluster to Rancher and get a kubeconfig file

Log-in to your Rancher deployment on the management server.

Add cluster > Import existing cluster > Follow instructions in the UI

Click on the cluster and then on kubeconfig file.

Download the file locally.

## Initialize a new ckan-cloud-operator environment

### Prerequisites
TODO

### Install ckan-cloud-operator
Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use with kubeconfig file.

### Initialize the cluster
Then run interactive initialization of the currently connected cluster:
```
ckan-cloud-operator cluster initialize --interactive
```

While interactive initialization:
- If environment is production, set `env-id` to `p` on "routers" step.
- On "solr" step of interactive initialization choose `self-hosted: y`


## Optional: install sample CKAN instance
TODO
