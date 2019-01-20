# Creating a Production CKAN Cloud cluster using Google Cloud services

## Create the Kubernetes cluster

Use the Google Kubernetes Engine web-ui to create a Kubernetes cluster

The following configuration was tested:

* Master Version: 1.10
* Number of nodes: 3
* Machine type: 4vCpu, 15GB RAM
* Auto-upgrade: on
* Enable VPC-native (using alias IP)
* Enable logging and monitoring

## Create the DB

Use the Google Cloud SQL web-ui to create a DB instance

The following configuration was tested:

* PostgreSQL 9.6
* Same zone as the Kubernetes cluster
* Connect using private IP only
* Machine type: 4vCPU, 15GM RAM
* Storage type: SSD
* High availability
* Automatic backups

## Install the management server

The management server is an optional but recommended component which provides management services for the cluster.

Follow [this guide](https://github.com/ViderumGlobal/ckan-cloud-cluster/blob/master/docs/MANAGEMENT.md) to create the server and deploy Rancher and Jenkins on it.

## Import the cluster to Rancher and get a kubeconfig file

Log-in to your Rancher deployment on the management server.

Add cluster > Import existing cluster > Follow instructions in the UI

Click on the cluster and then on kubeconfig file.

Download the file locally.

## Initialize a new ckan-cloud-operator environment

Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use this kubeconfig file.

Make sure to install the custom resource definitions and initialize the cluster as guided in the README.

Create an admin user for yourself:

```
ckan-cloud-operator users create your.name admin
```

Get the kubeconfig file for your admin user:

```
ckan-cloud-operator users get your.name > /path/to/your.kube-config
```

Replace the kube-config file for your environment with the newly created kube-config.

You should use the ckan-cloud-operator generated kube-config for increased security and audit logs.
