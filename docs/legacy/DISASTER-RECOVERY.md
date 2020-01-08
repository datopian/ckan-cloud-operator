# Disaster Recovery

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
