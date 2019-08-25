# Ckan Cloud Operator documentation
CKAN Cloud operator (CCO) manages, provisions and configures Ckan Cloud instances and related infrastructure.

# Table of contents
   * [DevOps Giude](#devops-giude)
      * [Installation and quick start](#installation-and-quick-start)
      * [Usage](#usage)
      * [Supported clouds](#supported-clouds)
      * [Initial set up of the cluster](#initial-set-up-of-the-cluster)
         * [Create the Kubernetes cluster](#create-the-kubernetes-cluster)
         * [Create the DB](#create-the-db)
         * [Install the management server](#install-the-management-server)
         * [Import the cluster to Rancher and get a kubeconfig file](#import-the-cluster-to-rancher-and-get-a-kubeconfig-file)
         * [Create multi-user storage class](#create-multi-user-storage-class)
         * [Initialize a new ckan-cloud-operator environment](#initialize-a-new-ckan-cloud-operator-environment)
            * [Prerequisites](#prerequisites)
            * [Install ckan-cloud-operator](#install-ckan-cloud-operator)
            * [Initialize the cluster](#initialize-the-cluster)
         * [Optional: enable autoscaling](#optional-enable-autoscaling)
         * [Optional: install sample CKAN instance](#optional-install-sample-ckan-instance)
            * [Put SOLR schema configs:](#put-solr-schema-configs)
            * [Prepare Gitlab repo:](#prepare-gitlab-repo)
            * [Prepare datapushers](#prepare-datapushers)
            * [Optional: prepare GCloud SQL proxy (if you use private IP)](#optional-prepare-gcloud-sql-proxy-if-you-use-private-ip)
            * [Create instance](#create-instance)
            * [Create routes, set up subdomains](#create-routes-set-up-subdomains)
   * [User Guide](#user-guide)
      * [Infrastructure management](#infrastructure-management)
         * [DB Instances](#db-instances)
         * [DB Connection pooler - PgBouncer](#db-connection-pooler---pgbouncer)
         * [Load Balancers and routing](#load-balancers-and-routing)
            * [List routers:](#list-routers)
            * [Get routes for an instance:](#get-routes-for-an-instance)
            * [Create a router](#create-a-router)
            * [Delete route:](#delete-route)
         * [Storage management](#storage-management)
         * [Setting Infrastructure container spec overrides](#setting-infrastructure-container-spec-overrides)
      * [Instance management](#instance-management)
         * [CKAN management](#ckan-management)
         * [SOLR management](#solr-management)
         * [Storage management](#storage-management-1)
         * [DB management](#db-management)
         * [Datapusher management](#datapusher-management)
         * [CRUD operations](#crud-operations)
               * [create instance](#create-instance-1)
               * [list instances](#list-instances)
               * [Get instance details and health:](#get-instance-details-and-health)
               * [Edit instance spec](#edit-instance-spec)
         * [Instance routing](#instance-routing)
         * [Low-level objects and operations](#low-level-objects-and-operations)
      * [Disaster Recovery](#disaster-recovery)
         * [CKAN Instance recovery](#ckan-instance-recovery)
         * [Restore Minio Storage](#restore-minio-storage)
         * [Create Database Backup](#create-database-backup)
         * [Full DB cluster backups](#full-db-cluster-backups)
         * [Scheduled DB backups](#scheduled-db-backups)
         * [Kubernetes and volume snapshots](#kubernetes-and-volume-snapshots)
         * [DB Backup data verification](#db-backup-data-verification)
      * [Contributing](#contributing)
      * [Features wanted](#features-wanted)


# DevOps Giude
![infra overview](https://github.com/datopian/ckan-cloud-operator/raw/full-documentation/docs/resources/infra_overview.png)

All the requirements needed to smoothly run CKAN instances runs inside `ckan-cloud` namespace.  
Each CKAN instance has it's own namespace.

For each of CKAN intance there should be a Gitlab repo contains `Dockerfile` and `.env` file (which stores CKAN settings).  
CCO creates or updates CKAN instance from the Docker image built on Gitlab CI.

## Installation and quick start
`ckan-cloud-operator-env` is used to install and manage CKAN Cloud operator environments on your local PC

**Prerequisites:**

* `.kube-config` file with permissions to the relevant cluster

Install latest ckan-cloud-operator-env

```
curl -s https://raw.githubusercontent.com/datopian/ckan-cloud-operator/master/ckan-cloud-operator-env.sh \
| sudo tee /usr/local/bin/ckan-cloud-operator-env >/dev/null && sudo chmod +x /usr/local/bin/ckan-cloud-operator-env
```

Add an environment (sudo is required to install the executable)

```
sudo ckan-cloud-operator-env add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE>
```

Verify conection to the cluster and installed operator version (may take a while on first run or after upgrade of operator version)

```
ckan-cloud-operator cluster info
```

**Important** Re-run the add command and cluster info to verify compatible version is installed.

## Usage
Use the CLI help messages for the reference documentation and usage examples.

```
ckan-cloud-operator --help
ckan-cloud-operator deis-instance --help
```

## Supported clouds
Currently these cloud providers are supported:
- Google Cloud (GKE)
- AWS (AKS)

## Initial set up of the cluster
### Create the Kubernetes cluster
Use the Google Kubernetes Engine web-ui to create a Kubernetes cluster

The following configuration was tested:

* Master Version: 1.11
* Number of nodes: 3
* Machine type: 4vCpu, 15GB RAM
* Auto Upgrade: off
* Auto Repair: off
* Enable VPC-native (using alias IP)
* Enable logging and monitoring using Stackdriver Kubernetes monitoring

### Create the DB
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

### Install the management server
The management server is an optional but recommended component which provides management services for the cluster.

Follow [this guide](https://github.com/ViderumGlobal/ckan-cloud-cluster/blob/master/docs/MANAGEMENT.md) to create the server and deploy Rancher and Jenkins on it.

### Import the cluster to Rancher and get a kubeconfig file
Log-in to your Rancher deployment on the management server.

Add cluster > Import existing cluster > Follow instructions in the UI

Click on the cluster and then on kubeconfig file.

Download the file locally.

### Create multi-user storage class
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

### Initialize a new ckan-cloud-operator environment
#### Prerequisites
1. Need to save Service Account key (JSON)
2. Need to have `gcloud` command in PATH
3. Need to have a domain and a CloudFlare account
4. Need to have a StatusCake account
5. Prepare separate kubeconfig to be used by Deis (could be done after cluster initialization)
6. Create storage bucket in advance (name it `ckan-storage-import-bucket` for example)
7. Prepare Gitlab access token (readonly permissions)
8. Prepare CloudFlare access token

#### Install ckan-cloud-operator
Follow the ckan-cloud-operator installation and usage guide in the [README.md](/README.md) to configure ckan-cloud-operator to use with kubeconfig file.

#### Initialize the cluster
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

### Optional: enable autoscaling
First, read the docs [here](https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-autoscaler).

Read help and enable built-in autoscaler if needed:
```
ckan-cloud-operator cluster setup-autoscaler --help
```

### Optional: install sample CKAN instance
#### Put SOLR schema configs:
```
cd ~/dev
git clone https://github.com/ckan/ckan.git
# optionally switch to another branch if you don't want `master`
# cd ~/dev/ckan && git checkout ckan-2.8.2
ckan-cloud-operator solr zk put-configs ~/dev/ckan
```

#### Prepare Gitlab repo:
1. Copy or fork from existing repo (for example `viderum/cloud-lithuania`)
2. Update parameters in `.env` file inside the repo and push to master
3. Make sure Gitlab CI ran successfully and pushed the image

#### Prepare datapushers
Optional: if datapushers registry is outside gitlab organization you configured during cluster setup, create docker registry secret to retrieve datapusher images:
```
kubectl -n ckan-cloud create secret docker-registry datapushers-docker-registry --docker-server=registry.gitlab.com --docker-username=<username> --docker-password=<personal access token> --docker-email=<email>
```

Initialize datapushers:
```
ckan-cloud-operator datapushers initialize
```

#### Optional: prepare GCloud SQL proxy (if you use private IP)
```
ckan-cloud-operator db gcloudsql initialize --interactive --db-prefix demo
ckan-cloud-operator db proxy port-forward --db-prefix demo
```

#### Create instance
```
ckan-cloud-operator deis-instance create from-gitlab <repo> ckan/config/schema.xml ckandemo --db-prefix demo
```

Optionally add `--use-private-gitlab-repo` if the repo you passed is outside the organization you configured during cluster setup (e.g. forked to your private account). You will be asked to provide your gitlab deploy token.

#### Create routes, set up subdomains
Follow the steps [here](https://github.com/datopian/ckan-cloud-operator/blob/master/docs/INSTANCE-MANAGEMENT.md#create-instance) to create internal/external instance routes


# User Guide

## Infrastructure management

### DB Instances

DB Instances are namespaced by an optional prefix

Initialize a new DB instance with given PREFIX:

```
ckan-cloud-operator db gcloudsql initialize --interactive --db-prefix PREFIX
```

To move an existing instance DB to a new instance, see the [disaster recovery](#disaster-recovery) section, add `--db-prefix` argument to the create command.

When using a prefixed DB locally, ensure you start a proxy for this DB as well:

```
ckan-cloud-operator db proxy port-forward --db-prefix PREFIX
```


### DB Connection pooler - PgBouncer
```
psql -d `ckan-cloud-operator db connection-string --admin`
postgres=> \connect pgbouncer
pgbouncer=# show lists;
pgbouncer=# show pools;
pgbouncer=# show help;
```


### Load Balancers and routing

#### List routers:
```
ckan-cloud-operator routers list
```

List routers with full details including all related routes:

```
ckan-cloud-operator routers list --full
```

#### Get routes for an instance:
```
ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID
```

edit route specs:

```
EDITOR=nano ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID --edit
```

#### Create a router
Create an external domains router which is backed by a dedicated load balancer:

```
ckan-cloud-operator routers create-traefik-router ROUTER_NAME --external-domains
```

Route an instance through this router for a specified external domain:

```
ckan-cloud-operator routers create-deis-instance-subdomain-route ROUTER_NAME DEIS_INSTANCE_ID SUB_DOMAIN ROOT_DOMAIN
```

Other type of routes can be created as well, see `ckan-cloud-operator routers --help`

#### Delete route:
Get the routes related to an instance:

```
ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID
```

Delete the relevant route name (a hash that starts with cc...)

```
ckan-cloud-operator kubectl -- delete ckancloudroute "cc..."
```

Update the relevant router for the change to take effect:

```
ckan-cloud-operator routers update ROUTER_NAME --wait-ready
```


### Storage management
Storage management can be done from a pod which is deployed on the cluster, or locally

Using Rancher, deploy the minio client container (if it doesn' exist):

* name: `minio-mc`
* namespace: `ckan-cloud`
* image: `minio/mc`
* command entrypoint: `/bin/sh -c 'while true; do sleep 86400; done'`

Add `prod` minio host:

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc config host add prod `ckan-cloud-operator storage credentials --raw`
```

List bucket policies

```
mc policy list prod/ckan
```

Depending on instance, some paths can be set to public download:

```
mc policy download prod/ckan/instance/storage'*'
```

### Setting Infrastructure container spec overrides
See Jupyter Lab notebooks for setting solrcloud and minio resources


## Instance management
* Verify connection to the cluster
  * `ckan-cloud-operator cluster info`
* Verify connection to an instance DB
  * `psql -d $(ckan-cloud-operator db connection-string --deis-instance INSTANCE_ID)`
* Verify Google Cloud authentication
  * `gsutil ls`
  * `gcloud container clusters list`


### CKAN management
Run a bash shell on the instance's pod:

```
ckan-cloud-operator deis-instance ckan exec INSTANCE_ID -- -it bash
```

Get last 10 log lines:

```
ckan-cloud-operator deis-instance ckan logs INSTANCE_ID -- --tail=10
```

See additional log options:

```
ckan-cloud-operator deis-instance ckan logs INSTANCE_ID -- --help
```

Get list of available paster commands:

```
ckan-cloud-operator deis-instance ckan paster INSTANCE_ID
```

Run a paster command:

```
ckan-cloud-operator deis-instance ckan paster INSTANCE_ID -- plugin-info
```


### SOLR management
Use the search-index command to rebuild or fix the index:

```
ckan-cloud-operator deis-instance ckan paster INSTANCE_ID -- search-index --help
```

SOLR web-ui is available via a port-forward:

```
ckan-cloud-operator solr solrcloud-port-forward
```

Access at http://localhost:8983


### Storage management
Get the storage admin credentials:

```
ckan-cloud-operator storage credentials
```

Log-in to Minio using the web UI or using [Minio Client](https://docs.minio.io/docs/minio-client-quickstart-guide.html)


### DB management
Connect to the instance DBs with the different users:

```
ckan-cloud-operator deis-instance ckan exec INSTANCE_ID -- -it bash
psql -d $CKAN_SQLALCHEMY_URL
psql -d $CKAN__DATASTORE__WRITE_URL
psql -d $CKAN__DATASTORE__READ_URL
```


### Datapusher management
Get the datapusher URL:

```
ckan-cloud-operator deis-instance ckan exec datahub -- -it -- bash -c "'echo \$CKAN__DATAPUSHER__URL'"
```

The datapusher is parsed from the CKAN__DATAPUSHER__URL defined in the .env file:

The url must be in the format: `DATAPUSHER_NAME.ckan.io` or `DATAPUSHER_NAME.l3.ckan.io`

Where `DATAPUSHER_NAME` must match one of the datapushers installed on the environment

To get the list of available datapushers:

```
ckan-cloud-operator datapushers list
```


### CRUD operations
##### create instance

* Using Minio Web-UI or client - create the storage path (`/ckan/INSTANCE_ID`) and set permissions (might be different between instances, see permissions of other instasnces of the same type)
* Determine the required SOLR schema config (see the list or available configs at the SOLR web-ui Cloud > Tree > /configs)
* Create a GitLab app instance project, it should contain the following which can be copied from another project and modified:
  * `.env` file
  * `Dockerfile`
  * `.gitlab-ci.yml`
* Make sure gitlab CI ran successfully and pushed the image

Create the instance:

```
ckan-cloud-operator deis-instance create from-gitlab GITLAB_REPO SOLR_SCHEMA_CONFIG NEW_INSTANCE_ID
```

The following options are supported to modify the created instance:

* `--db-prefix PREFIX` - supports multiple DB instances, see [DB Infrastructure management](/docs/INFAR-MANAGEMENT.md) for more details

Add the default, internal instance route (`https://cc-?-INSTANCE_ID.DEFAULT_ROOT_DOMAIN`):

```
ckan-cloud-operator routers create-deis-instance-subdomain-route instances-default NEW_INSTANCE_ID --wait-ready
```

Add an external route (Make sure DNS is configured and propogated before):

```
ckan-cloud-operator routers create-deis-instance-subdomain-route EXTERNAL_DOMAINS_ROUTER_NAME DEIS_INSTANCE_ID EXTERNAL_SUB_DOMAIN EXTERNAL_ROOT_DOMAIN
```

This command can also be used to restore from backup or changing storage paths or solr collections, see [CKAN Instance Recovery](https://github.com/datopian/ckan-cloud-operator/blob/master/docs/DISASTER-RECOVERY.md#ckan-instance-recovery).

[Migration doc](https://github.com/datopian/ckan-cloud-operator/blob/master/docs/IMPORT-DEIS.md) also contain useful details to troubleshoot or debug instance creation.

##### list instances

```
ckan-cloud-operator deis-instance list -q  # quick list, without checking status
ckan-cloud-operator deis-instance list -f  # full yaml list with configuration, status and health details
```

##### Get instance details and health:

```
ckan-cloud-operator deis-instance get INSTANCE_ID
```

##### Edit instance spec

```
ckan-cloud-operator deis-instance edit INSTANCE_ID
```

Following changes can be done to the spec:

**override container spec**

Set specific CKAN Docker image:

```
  ckanContainerSpec:
    image: DOCKER_IMAGE
```

Set container resources:

```
  ckanContainerSpec:
    resources:
      limits:
        memory: 3Gi
      requests:
        memory: 2Gi
```

See [kubernetes api: container](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.11/#container-v1-core).

**container env vars - from a secret**

```
  envvars:
    fromSecret: secret-name-in-instance-namespace
```

**container env vars - from gitlab**

gets the env vars from `.env` file in the gitlab project

```
  envvars:
    fromGitlab: GITLAB_PROJECT
```


### Instance routing

Get all routes related to an instance:

```
ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID
```


### Low-level objects and operations

```
ckan-cloud-operator kubectl -- get CkanCloudCkanInstance INSTANCE_ID -o yaml
```

instance spec can be modified directly (or using ckan-cloud-operator deis-instance edit):

```
spec:
  # overrides the ckan container spec
  ckanContainerSpec:
    image: registry.gitlab.com/viderum/cloud-datahub
  # overrides the ckan pod spec
  ckanPodSpec: {}
  datastore:
    # source migration object, not relevant after migration is complete
    fromDbMigration: deis-dbs-datahub-to-datahub--datahub-datastore
    # datastore DB name, can be modified to switch DBs (need to make sure it's created first)
    name: datahub-datastore
  db:
    # same as datastore
    fromDbMigration: deis-dbs-datahub-to-datahub--datahub-datastore
    name: datahub
  envvars:
    # envvars will are mounted to the pod environment directly from this secret
    fromSecret: datahub-envvars
    overrides:
      # override secret envvars
      CKAN_SITE_URL: https://datahub.ckan.io
  solrCloudCollection:
    # solr configuration, not relevant after collection was created
    configName: ckan_default
    # solr collection name
    name: datahub
  storage:
    # minio storage path
    path: /ckan/datahub
```

After update to kubernetes objects, run an instance update:

```
ckan-cloud-operator deis-instance update INSTANCE_ID
```

## Disaster Recovery
### CKAN Instance recovery

Get the DB backups bucket name and path:

```
BACKUPS_GS_BASE_URL=`ckan-cloud-operator config get --secret-name ckan-cloud-provider-db-gcloudsql-credentials --key backups-gs-base-url --raw`
echo $BACKUPS_GS_BASE_URL
```

List all backups from current day of an instance:

```
gsutil ls $BACKUPS_GS_BASE_URL/`date +%Y/%m/%d`/'*'/ | grep INSTANCE_ID
```

Storage path can usually be shared between the old and restored instances. See "Restore Minio Storage" if you need to restore storage for an instance.

SOLR collection can also be shared. If needed a new collection can be used, this will require a full search-index rebuild after the instance is created.

Get the current instance details: `ckan-cloud-operator kubectl -- get ckancloudckaninstance INSTANCE_ID -o yaml`

Create a new CKAN instance from backups

```
ckan-cloud-operator deis-instance create from-gitlab GITLAB_REPO SOLR_SCHEMA_CONFIG NEW_INSTANCE_ID \
    --from-db-backups DATABASE_GS_URL,DATASTORE_GS_URL \
    --storage-path /ckan/INSTANCE_ID \
    --solr-collection INSTANCE_ID
```

In case of failure, you can add `--rerun` / `--force` / `--recreate-dbs` arguments to rerun from last successful step or force / recreate. See [IMPORT-DEIS.md](/docs/IMPORT-DEIS.md) for more details about DB migrations.

To deploy on a different DB instance, add `--db-prefix DB_PREFIX`

To switch existing external domain to use the new instance -

Edit the routes associated with the old instance -

```
ckan-cloud-operator routers get-routes --deis-instance-id OLD_INSTANCE_ID --edit
```

For the route associated with the external domains router - change the instance id in all fields (be sure to update all fields, including labels, annotations and spec)

Update the router:

```
ckan-cloud-operator routers update ROUTER_NAME
```

See [IMPORT-DEIS.md](/docs/IMPORT-DEIS.md) for setting up an external route and more troubleshooting and configuration options.

Old instance can be deleted, SOLR, storage and DB will not be deleted: `ckan-cloud-operator deis-instance delete OLD_INSTANCE`

### Restore Minio Storage

Minio volume snapshots are created periodically using Ark / Velero.

Get the Minio persistent volume claim ID:

```
ckan-cloud-operator config get --configmap-name ckan-cloud-provider-storage-minio --key volume-spec --raw
```

Using Google Cloud web-ui, navigate to Compute Engine > Snapshots

Use the following filter query to get the relevant snapshots:

```
Source disk:PERSISTENT_VOLUME_CLAIM
```

Sort by creation time. The backups are incremental, if there are no changes, a snapshot is not created.

Click on a snapshot and copy the snapshot ID

Disks > Create Disk
  * Name: can be any name to identify the restore purpose
  * Type: Standard persistent disk
  * Region / Zone: Same as the Kubernetes cluster

Initialize a new Minio server based on this disk:

```
ckan-cloud-operator storage initialize --interactive --storage-suffix=UNIQUE_SUFFIX --disk-name=DISK_CREATED_FROM_SNAPSHOT
```

When storage suffix is used, the storage server is not exposed publically.

You can access it with a port-forward or add a route manually.

Use Minio Client `mirror` command to copy over specific paths.

Get the new Minio server credentials:

```
ckan-cloud-operator storage credentials --storage-suffix=UNIQUE_SUFFIX
```

To delete the server, get all the related objects and delete using kubectl:

```
ckan-cloud-operator kubectl -- \
    get all -l ckan-cloud/provider-id=minio,ckan-cloud/provider-submodule-suffix=STORAGE_SUFFIX
```

Get and delete the volume and persistent disk:

```
ckan-cloud-operator kubectl -- get pv,pvc GCLOUD_PERSISTENT_DISK_NAME
```

Delete the persistent disk using the Gcloud web-UI

### Create Database Backup

Backups are created with hourly timestamps, if 2 backups are run on the same hour, the latest backup will overwrite the previous backup.

Create a backup:

```
ckan-cloud-operator db gcloudsql create-backup <DATABASE_NAME>
```

### Full DB cluster backups

Full GcloudSQL instance backups are also available.

In case of extreme disasters the entire DB cluster can be restored via the Gcloud web-ui.

### Scheduled DB backups

Scheduled DB backups can run using Jenkins or similiar CI / job scheduler

Following script can be used to created a scheduled job using the [jenkins integration](https://github.com/datopian/ckan-cloud-operator/blob/master/docs/JENKINS.md):

Build triggers:

* Build periodically: `H H/6 * * *`
  * The interval of backups depends on how long it takes to make the backups
  * Jenkins won't run concurrent builds but it's better to make sure there is no queue of jobs
  * The backup files are created with a 2-hourly timestamp, so jobs should not be schedled in less then 2 hour intervals

Parameters:

* `DRY_RUN`: choices (yes/no)
* `CREATE_BACKUPS_AFTER_DRY_RUN`: choices (yes/no)

Execute shell:

```
#!/usr/bin/env bash

if [ "${DRY_RUN}" == "yes" ]; then
  echo Dry Run &&\
  ckan-cloud-operator db gcloudsql create-all-backups --dry-run
fi &&\
if [ "${DRY_RUN}" == "no" ] || [ "${CREATE_BACKUPS_AFTER_DRY_RUN}" == "yes" ]; then
  echo Creating all backups. This may take a while.. &&\
  ckan-cloud-operator db gcloudsql create-all-backups
fi
```


### Kubernetes and volume snapshots

ARK / Velero creates backups of Kubernetes objects and disk snapshots for persistent volume claims.

See [Heptio ARK / Velero documentation](https://heptio.github.io/velero/v0.11.0/) for installation / usage.

If you are connected to the relevant Kubernetes cluster, you can run `ark` commands:

List the scheduled backups:

```
ark schedule get
```

List the backups:

```
ark backup get
```

Use grep to get latest backups:

```
ark backup get | grep SCHEDULD_NAME-20190305
```

Get backup details:

```
ark backup describe --details BACKUP_NAME
```

Ark supports restoring the whole cluster:

```
ark restore
```


### DB Backup data verification

Create a new instance based on backups

Set some env vars and initialize the DB diff tool:

```
OLD_INSTANCE_ID=
NEW_INSTANCE_ID=
DIFF_FOLDER=/tmp/dbdiff_$OLD_INSTANCE_ID

mkdir -p $DIFF_FOLDER/db
mkdir -p $DIFF_FOLDER/datastore

alias postgresdbdiff.py="python -m ckan_cloud_operator.drivers.postgresdbdiff"
```

Compare main DB

```
postgresdbdiff.py \
    --db1 `ckan-cloud-operator db connection-string --deis-instance $OLD_INSTANCE_ID` \
    --db2 `ckan-cloud-operator db connection-string --deis-instance $NEW_INSTANCE_ID` \
    --rowcount --diff-folder $DIFF_FOLDER/db | tee -a $DIFF_FOLDER/db.log
```

Compare datastore DB

```
postgresdbdiff.py \
    --db1 `ckan-cloud-operator db connection-string --deis-instance $OLD_INSTANCE_ID --datastore` \
    --db2 `ckan-cloud-operator db connection-string --deis-instance $NEW_INSTANCE_ID --datastore` \
    --rowcount --diff-folder $DIFF_FOLDER/datastore | tee -a $DIFF_FOLDER/datastore.log
```

## Contributing
Report any issues and problems you found on repo's "Issues" section.  
Include full description of the issue including related logs and traces. Don't forget to include cluster info.

## Features wanted
1. CCO command to deploy custom (not Lets Encrypt) certificate on traefik for a domain.
2. Deploy Ark/Velero (used for backups) as a part of infractructure on cluster initialization
