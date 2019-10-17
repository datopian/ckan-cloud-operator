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

## Create multi-user storage class

This is used for small volume storage for shared configurations / infrastructure

1. Create service account for Tiller:
```
kubectl -n kube-system create sa tiller
kubectl create clusterrolebinding tiller --clusterrole cluster-admin --serviceaccount=kube-system:tiller
helm init --service-account tiller
```

2. Download and init helm on your cluster:
```
curl -LO https://git.io/get_helm.sh
chmod 700 get_helm.sh
./get_helm.sh
helm init
helm repo update
```

3. Deploy `nfs-server-provisioner` helm chart (can use Rancher catalog app) with the following values:
```
persistence.enabled = true
persistence.size = 500Gi
storageClass.name = cca-ckan
```

Or from command line:
```
helm install --namespace=ckan-cloud stable/nfs-server-provisioner --name cloud-nfs --set=persistence.enabled=true,persistence.size=500Gi,storageClass.name=cca-ckan
```

## Initialize a new ckan-cloud-operator environment

### Prerequisites
TODO

### Install ckan-cloud-operator
Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use with kubeconfig file.

### Initialize the cluster
First,
```
kubectl create namespace ckan-cloud
kubectl -n ckan-cloud create secret generic ckan-cloud-provider-cluster-gcloud
kubectl -n ckan-cloud create configmap operator-conf --from-literal=ckan-cloud-operator-image=viderum/ckan-cloud-operator:latest --from-literal=label-prefix=ckan-cloud
```

After that create `uptime-statuscake-api` secrets with keys "user", "key", "group" populated from StatusCake account:
```
kubectl -n ckan-cloud create secret generic uptime-statuscake-api --from-literal=user=<user> --from-literal=key=<key> --from-literal=group=<group>
```

Then run interactive initialization of the currently connected cluster:
```
ckan-cloud-operator cluster initialize --interactive
```

While interactive initialization:
- Set `enable-deis-ckan: y`
- If environment is production, set `env-id` to `p` on "routers" step.
- On "solr" step of interactive initialization choose `self-hosted: y`
- On "ckan" step when asked for docker server/username/password, enter your Gitlab credentials, password should be your Gitlab access token.


Give the service account permission to change cluster roles:
```
kubectl create clusterrolebinding default-sa-binding --clusterrole=cluster-admin --user=<service account email>
```

Create an admin user:

```
ckan-cloud-operator users create your.name --role=admin
```

Get the kubeconfig file for your admin user:
```
ckan-cloud-operator users get-kubeconfig your.name > /path/to/your.kube-config
```
**Warning:** `/path/to/your.kube-config` should not be equal to your current kubeconfig file, otherwise you'll lost your kubeconfig and not receive new kubeconfig. 

Replace the kube-config file for your environment with the newly created kube-config.

You should use the ckan-cloud-operator generated kube-config for increased security and audit logs.

## Optional: install sample CKAN instance
TODO
