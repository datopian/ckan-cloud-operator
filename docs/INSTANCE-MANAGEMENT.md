# Instance Management


## Prerequisites

* Installed ckan-cloud-operator according to the [README](/README.md)

Start a ckan-cloud-operator shell:

```
ckan-cloud-operator bash
```

**All the following commands should run from within a ckan-cloud-operator shell**

* Verify connection to the cluster
  * `ckan-cloud-operator cluster info`
* Verify connection to an instance DB
  * `psql -d $(ckan-cloud-operator db connection-string --deis-instance INSTANCE_ID)`
* Verify Google Cloud authentication
  * `gsutil ls`
  * `gcloud container clusters list`


## CKAN management

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


## SOLR management

Use the search-index command to rebuild or fix the index:

```
ckan-cloud-operator deis-instance ckan paster INSTANCE_ID -- search-index --help
```

SOLR web-ui is available via a port-forward:

```
ckan-cloud-operator solr solrcloud-port-forward
```

Access at http://localhost:8983


## Storage management

Get the storage admin credentials:

```
ckan-cloud-operator storage credentials
```

Log-in to Minio using the web UI or using [Minio Client](https://docs.minio.io/docs/minio-client-quickstart-guide.html)


## DB management

Connect to the instance DBs with the different users:

```
ckan-cloud-operator deis-instance ckan exec INSTANCE_ID -- -it bash
psql -d $CKAN_SQLALCHEMY_URL
psql -d $CKAN__DATASTORE__WRITE_URL
psql -d $CKAN__DATASTORE__READ_URL
```


## Datapusher management

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


## CRUD operations

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

This command can also be used to restore from backup or changing storage paths or solr collections, see [CKAN Instance Recovery](https://github.com/ViderumGlobal/ckan-cloud-operator/blob/master/docs/DISASTER-RECOVERY.md#ckan-instance-recovery).

[Migration doc](https://github.com/ViderumGlobal/ckan-cloud-operator/blob/master/docs/IMPORT-DEIS.md) also contain useful details to troubleshoot or debug instance creation.

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


## Instance routing

Get all routes related to an instance:

```
ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID
```


## low-level objects and operations

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

