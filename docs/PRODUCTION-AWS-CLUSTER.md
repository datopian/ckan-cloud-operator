# Creating a Production CKAN Cloud cluster using Amazon Kubernetes service

## Prerequisites

* An Amazon Kubernets cluster connected to Rancher according to [ckan-cloud-cluster docs](https://github.com/ViderumGlobal/ckan-cloud-cluster/blob/master/docs)
  * At least 3 `m4.xlarge` nodes in the same availability zone

## Get the kubeconfig file

Click on the cluster and then on kubeconfig file.

Download the file locally.

## Initialize a new ckan-cloud-operator environment

Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use this kubeconfig file.

Run interactive initialization of the currently connected cluster using AWS infrastructure providers:

```
ckan-cloud-operator cluster initialize --interactive --cluster-provider aws
```

Initialize the users module, based on Rancher API

```
ckan-cloud-operator users initialize --interactive
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


## Optional: enable autoscaling
Read help and install `stable/cluster-autoscaler` helm package on cluster if needed by using CCO command:
```
ckan-cloud-operator cluster setup-autoscaler --help
```
