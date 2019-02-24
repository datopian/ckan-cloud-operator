# Creating a Production CKAN Cloud cluster using Google Cloud services

## Create the Kubernetes cluster

Use the Google Kubernetes Engine web-ui to create a Kubernetes cluster

The following configuration was tested:

* Master Version: 1.11
* Number of nodes: 3
* Machine type: 4vCpu, 15GB RAM
* Auto Upgrade: off
* Auto Repair: off
* Enable VPC-native (using alias IP)
* Enable logging and monitoring using Stackdriver Kubernetes monitoring

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

## Create multi-user storage class

This is used for small volume storage for shared configurations / infrastructure

Deploy nfs-server-provisioner helm chart (can use Rancher catalog app) with the following values:

```
persistence.enabled = true
persistence.size = 5Gi
storageClass.name = cca-ckan
```

## Initialize a new ckan-cloud-operator environment

Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use this kubeconfig file.

Run interactive initialization of the currently connected cluster

```
ckan-cloud-operator cluster initialize --interactive
```


Create an admin user:

```
ckan-cloud-operator users create your.name --role=admin
```

Get the kubeconfig file for your admin user:

```
ckan-cloud-operator users get-kubeconfig your.name > /path/to/your.kube-config
```

Replace the kube-config file for your environment with the newly created kube-config.

You should use the ckan-cloud-operator generated kube-config for increased security and audit logs.
