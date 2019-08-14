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
* Connectivity: Private IP

Optional: if you enabled "Public IP", add your IP/network inside the SQL instance "Connections" tab ("Authorized networks").


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
persistence.size = 5Gi
storageClass.name = cca-ckan
```

Or from command line:
```
helm install --namespace=ckan-cloud stable/nfs-server-provisioner --name cloud-nfs --set=persistence.enabled=true,persistence.size=5Gi,storageClass.name=cca-ckan
```

## Initialize a new ckan-cloud-operator environment

### Prerequisites
1. Need to save Service Account key (JSON)
2. Need to have `gcloud` command in PATH
3. Need to have a domain and a CloudFlare account
4. Need to have a StatusCake account
5. Prepare separate kubeconfig to be used by Deis (could be done after cluster initialization)
6. Create storage bucket in advance (name it `ckan-storage-import-bucket` for example)
7. Prepare Gitlab access token (readonly permissions)
8. Prepare CloudFlare access token

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

## Optional: enable autoscaling
First, read the docs [here](https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-autoscaler).

Read help and enable built-in autoscaler if needed:
```
ckan-cloud-operator cluster setup-autoscaler --help
```

## Optional: install sample CKAN instance
### Put SOLR schema configs:
```
cd ~/dev
git clone https://github.com/ckan/ckan.git
# optionally switch to another branch if you don't want `master`
# cd ~/dev/ckan && git checkout ckan-2.8.2
ckan-cloud-operator solr zk put-configs ~/dev/ckan
```

### Prepare Gitlab repo:
1. Copy or fork from existing repo (for example `viderum/cloud-lithuania`)
2. Update parameters in `.env` file inside the repo and push to master
3. Make sure Gitlab CI ran successfully and pushed the image

### Prepare datapushers
Optional: if datapushers registry is outside gitlab organization you configured during cluster setup, create docker registry secret to retrieve datapusher images:
```
kubectl -n ckan-cloud create secret docker-registry datapushers-docker-registry --docker-server=registry.gitlab.com --docker-username=<username> --docker-password=<personal access token> --docker-email=<email>
```

Initialize datapushers:
```
ckan-cloud-operator datapushers initialize
```

### Optional: prepare GCloud SQL proxy (if you use private IP)
```
ckan-cloud-operator db gcloudsql initialize --interactive --db-prefix demo
ckan-cloud-operator db proxy port-forward --db-prefix demo
```

### Create instance
```
ckan-cloud-operator deis-instance create from-gitlab <repo> ckan/config/schema.xml ckandemo --db-prefix demo
```

Optionally add `--use-private-gitlab-repo` if the repo you passed is outside the organization you configured during cluster setup (e.g. forked to your private account). You will be asked to provide your gitlab deploy token.

### Create routes, set up subdomains
Follow the steps [here](https://github.com/datopian/ckan-cloud-operator/blob/master/docs/INSTANCE-MANAGEMENT.md#create-instance) to create internal/external instance routes
