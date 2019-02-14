# Importing deis instances to ckan-cloud on GKE

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

see ckan-cloud-dataflows for importing the configs to searchstax - all configs should be imported already

## Deploy the Minio server

```
ckan-cloud-operator storage initialize --interactive
```

Get the credentials

```
ckan-cloud-operator storage credentials
```

Get the Deis cluster credentials (on edge cluster):

```
ckan-cloud-operator config get --secret-name deis-minio-credentials
```

Using Rancher, deploy a minio client image (`docker image = minio/mc`) and execute a shell on it

Run the following inside the minio client shell to setup the relevant hosts

```
mc config host add edge https://cc-e-minio.ckan.io MINIO_ACCESS_KEY MINIO_SECRET_KEY
mc config host add deis https://minio.l3.ckan.io MINIO_ACCESS_KEY MINIO_SECRET_KEY
```

Create the bucket and mirror the data

```
mc mirror --overwrite --watch -a deis/ckan edge/ckan
```

* `-a` = keep storage policies


## migrate an instance

Assuming:

* you used previous stesp to prepare the import data for all instances
* ckan-cloud-operator is configured with required secrets to support the migration

Start the DB proxy (keep running in the background)

```
ckan-cloud-operator db proxy port-forward
```

Migrate an instance:

```
ckan-cloud-operator ckan migrate-deis-instance OLD_SITE_ID
```

If migration fails or when making changes, you can rerun with following flags:

* `--recreate` - delete instance and DBs and recreate from scratch
* `--rerun` - re-run the migration, but doesn't re-migrate DBs and skips some components if already exist
* `--recreate-instance` - delete and re-create the instance (but not the DBs)

Skip specific parts of the migration:

* `--skip-gitlab`
* `--skip-routes`
* `--skip-solr`
* `--skip-deployment`
