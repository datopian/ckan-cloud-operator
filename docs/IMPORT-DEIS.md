# Importing deis instances to ckan-cloud on GKE

## Prepare Gcloud SQL for import via Google Store bucket

Get the service account email for the cloud sql instance (you should be authorized to the relevant Google account)

```
GCLOUD_SQL_INSTANCE_ID=

GCLOUD_SQL_SERVICE_ACCOUNT=`gcloud sql instances describe $GCLOUD_SQL_INSTANCE_ID \
    | python -c "import sys,yaml; print(yaml.load(sys.stdin)['serviceAccountEmailAddress'])" | tee /dev/stderr`
```

Give permissions to the bucket used for importing:

```
GCLOUD_SQL_DUMPS_BUCKET=

gsutil acl ch -u ${GCLOUD_SQL_SERVICE_ACCOUNT}:W gs://${GCLOUD_SQL_DUMPS_BUCKET}/ &&\
gsutil acl ch -R -u ${GCLOUD_SQL_SERVICE_ACCOUNT}:R gs://${GCLOUD_SQL_DUMPS_BUCKET}/
```

## Import DBs from Deis

Connect to the Deis cluster

```
DEIS_KUBECONFIG=/path/to/deis/.kube-config

KUBECONFIG=$DEIS_KUBECONFIG kubectl get nodes
```

Download the db operations pod yaml: https://github.com/ViderumGlobal/ckan-cloud-dataflows/blob/master/db-operations/pod.yaml

Edit and modify the pod name to the a unique, personal name (it uses your personal gcloud credentials)

Deploy a db-operations pod

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl apply -f /path/to/db_operations_pod.yaml
```

Login to the pod:

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec -it <DB_OPERATIONS_POD_NAME> -c db -- bash -l
```

Follow the interactive gcloud initialization

Get the db urls from the instance .env file

Set details of source instance and id for the dump files:

```
# DB sqlalchemy url (from the .env file)
DB_URL=

# DataStore sqlalchemy url (from the .env file)
DATASTORE_URL=

# old deis instance id
SITE_ID=
```

Dump the DBs and upload to cloud storage using the current date and site id (may take a while):

```
source functions.sh
dump_dbs $SITE_ID $DB_URL $DATASTORE_URL && upload_db_dumps_to_storage $SITE_ID
```

Copy the output containing the gs:// urls - you will need them to create the import configuration

Dump files are stored locally in the container and will be removed when db-operations pod is deleted

## Get the instance's solrcloud config name

Get the instance solr config name

```
# you can get the collection name from the instance env vars solr connection url
COLLECTION_NAME=

KUBECONFIG=$DEIS_KUBECONFIG kubectl -n solr exec zk-0 zkCli.sh get /collections/$COLLECTION_NAME
```

The output should contain a config name like `ckan_27_default`

see ckan-cloud-dataflows for importing the configs to searchstax - all configs should be imported already

## Sync storage from minio

Start a bash terminal with gcloud on the deis minio pod

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n deis exec -it deis-minio-6ddd8f5d85-wphhb bash
```

Use gcloud CLI to sync data, following command syncs all the data

```
cd /export &&\
gsutil -m rsync -R ./ gs://ckan-cloud-staging-storage/
```

Sync a single instance

```
cd /export &&\
gsutil -m rsync -R ./ckan/<INSTANCE_ID>/ gs://ckan-cloud-staging-storage/ckan/<INSTANCE_ID>/
```

## create an instance using ckan-cloud-operator

Use [ckan-cloud-operator](https://github.com/ViderumGlobal/ckan-cloud-operator) to create an instance using deis-instance create from-gcloud-envvars command
