# Disaster Recovery

### CKAN Instance recovery

Get the DB backups bucket name and path:

```
ckan-cloud-operator config get --secret-name ckan-cloud-provider-db-gcloudsql-credentials --key backups-gs-base-url
```

Browse the available backups using the Gcloud console storage web-ui.

Storage path can usually be shared between the old and restored instances. See "Restore Minio Storage" if you need to restore storage for an instance.

SOLR collection can also be shared. If needed a new collection can be used, this will require a full search-index rebuild after the instance is created.

Create a new CKAN instance from backups

```
ckan-cloud-operator deis-instance create from-gitlab GITLAB_REPO SOLR_SCHEMA_CONFIG NEW_INSTANCE_ID \
    --from-db-backups DATABASE_GS_URL,DATASTORE_GS_URL \
    --storage-path /ckan/INSTANCE_ID \
    --solr-collection INSTANCE_ID
```

In case of failure, you can add `--rerun` / `--force` / `--recreate-dbs` arguments to rerun from last successful step or force / recreate. See [IMPORT-DEIS.md](/docs/IMPORT-DEIS.md) for more details about DB migrations.

Add the default instance route:

```
ckan-cloud-operator routers create-deis-instance-subdomain-route instances-default NEW_INSTANCE_ID --wait-ready
```

See [IMPORT-DEIS.md](/docs/IMPORT-DEIS.md) for setting up an external route and more troubleshooting and configuration options.

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

Scheduled DB backups are run using a Kubernetes cronjob running a ckan-cloud-operator pod.

To create a ckan-cloud-operator pod:

* Create a kubeconfig file for the operator and set in a secret:
  * `kubectl -n ckan-cloud create secret generic operator-db-backups --from-file=.kubeconfig=/path/to/.kube-config`
* Deploy a cronjob using rancher:
  * scheduing: minimum of once every hour (as backups are created with hourly timestamp)
  * image: `viderum/ckan-cloud-operator` (recommended to use a specific image hash, see the ckan-cloud-operator travis job on GitHub)
  * volumes: mount the kubeconfig secret
  * environment variables: `KUBECONFIG=/path/to/.kubeconfig`
  * command: `db gcloudsql create-all-backups`

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
