# Importing deis instances to ckan-cloud on GKE

## Prepare Gcloud SQL for import via Google Store bucket

Authenticate to gcloud using ckan-cloud-operator

```
ckan-cloud-operator activate-gcloud-auth
```

Get the service account email for the cloud sql instance (you should be authorized to the relevant Google account)

```
GCLOUD_SQL_INSTANCE_ID=`ckan-cloud-operator ckan-infra get GCLOUD_SQL_INSTANCE_NAME`

GCLOUD_SQL_SERVICE_ACCOUNT=`gcloud sql instances describe $GCLOUD_SQL_INSTANCE_ID \
    | python -c "import sys,yaml; print(yaml.load(sys.stdin)['serviceAccountEmailAddress'])" | tee /dev/stderr`
```

Give permissions to the bucket used for importing:

```
GCLOUD_SQL_DEIS_IMPORT_BUCKET=`ckan-cloud-operator ckan-infra get GCLOUD_SQL_DEIS_IMPORT_BUCKET`

gsutil acl ch -u ${GCLOUD_SQL_SERVICE_ACCOUNT}:W gs://${GCLOUD_SQL_DEIS_IMPORT_BUCKET}/ &&\
gsutil acl ch -R -u ${GCLOUD_SQL_SERVICE_ACCOUNT}:R gs://${GCLOUD_SQL_DEIS_IMPORT_BUCKET}/
```

## Import DBs from Deis

Connect to the Deis cluster

```
DEIS_KUBECONFIG=/path/to/deis/.kube-config

KUBECONFIG=$DEIS_KUBECONFIG kubectl get nodes
```

Download the db operations pod yaml: https://github.com/ViderumGlobal/ckan-cloud-dataflows/blob/master/db-operations/pod.yaml

Use the following image for the cca-operator container: `orihoch/ckan-cloud-docker:cca-operator-db-import`

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

Run the following to create a script that imports all db instances based on deis config yamls:

```
INSTANCE_YAMLS_PATH="/path/to/instance/yamls/directory/"

echo source functions.sh '&&\' &&\
for YAML in $(ls $INSTANCE_YAMLS_PATH); do
    python3.6 -c '
import yaml
file_name = "'${YAML}'"
dir_name = "'${INSTANCE_YAMLS_PATH}'"
data = yaml.load(open("{}{}".format(dir_name, file_name)))
instance_id = file_name.replace(".yaml", "")
db_url = data.get("CKAN_SQLALCHEMY_URL")
datastore_url = data.get("CKAN__DATASTORE__WRITE_URL")
if db_url and datastore_url:
    print("echo '"'"'{}'"'"' && ( dump_dbs '"'"'{}'"'"' '"'"'{}'"'"' '"'"'{}'"'"' &&\\".format(instance_id, instance_id, db_url, datastore_url))
    print("upload_db_dumps_to_storage '"'"'{instance_id}'"'"') > '"'"'{instance_id}.logs'"'"'; echo $? > '"'"'{instance_id}.returncode'"'"'; ".format(instance_id=instance_id))
    print("rm -f *.dump.sql; ")
'
done &&\
echo '[ "$?" != "0" ] && echo Import failed'
```

Run the output script on the db-operations pod

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

**Use With Caution!** Sync all data, including file deletions

```
cd /export &&\
gsutil -m rsync -d -R ./ gs://ckan-cloud-staging-storage/
```

## Initialize the Minio storage proxy

```
ckan-cloud-operator initialize-storage
```

To debug minio and perform operations - start minio client shell:

```
docker run -it --entrypoint=/bin/sh minio/mc
```

Run the following inside the minio client shell to setup the relevant hosts

```
mc config host add prod https://cc-p-minio.ckan.io MINIO_ACCESS_KEY MINIO_SECRET_KEY
mc config host add deis https://minio.l3.ckan.io MINIO_ACCESS_KEY MINIO_SECRET_KEY
```



## Initialize the DataPusher

all datapushers were migrated, this step is probably not needed anymore, unless we find a new datapusher being used somewhere

Get the relevant DataPusher image from Rancher

ssh to one of the old cluster servers, tag and push the image to `registry.gitlab.com/viderum/docker-datapusher:cloud-<DATAPUSHER_IMAGE_TAG>`

Use the image to create the DataPusher using ckan-cloud-operator datapushers create command

## migrate the instance

Assuming:

* you used previous stesp to prepare the import data for all instances
* ckan-cloud-operator is configured with required secrets to support the migration

you can run the following to migrate an instance:

```
ckan-cloud-operator deis-instance create from-deis OLD_SITE_ID NEW_INSTANCE_ID
```
