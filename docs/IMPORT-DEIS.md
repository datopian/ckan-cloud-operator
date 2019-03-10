# Importing deis instances to ckan-cloud on GKE


## Prerequisites

##### ckan-cloud-operator

* Installed ckan-cloud-operator according to the [README](/README.md)
* Verified connection to the correct cluster:
  * `ckan-cloud-operator cluster info`

Start a ckan-cloud-operator shell:

```
ckan-cloud-operator bash
```

**All the following commands should run from within a ckan-cloud-operator shell**

* Verify connection to the DB
  * `psql -d $(ckan-cloud-operator db connection-string --admin)`
* Verify Google Cloud authentication
  * `gsutil ls`
  * `gcloud container clusters list`

##### Deis Cluster

Get the Deis Kubeconfig file

```
DEIS_KUBECONFIG=$(python -c 'from ckan_cloud_operator.providers.ckan import manager; print(manager.get_path_to_old_cluster_kubeconfig())' | tail -1)
```

Verify connection to the Deis cluster

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl get nodes
```

##### Deploy personal db operations pod on old cluster

Set name for the db operations pod, it should be a unique, personal name (it uses your personal gcloud credentials)

```
DB_OPERATIONS_POD="<YOUR_NAME>-db-operations"
```

Download the db operations pod yaml: https://github.com/ViderumGlobal/ckan-cloud-dataflows/blob/master/db-operations/pod.yaml

Use the following image for the cca-operator container: `orihoch/ckan-cloud-docker:cca-operator-db-import`

Edit and modify the pod name to the name you set in DB_OPERATIONS_POD

Deploy the pod

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl apply -f /path/to/db_operations_pod.yaml
```


##### Deploy the Minio client container

Most likely this step can be skipped as the same pod can be used by multiple users and was already deployed.

Using Rancher, deploy a minio client container:

* name: `minio-mc`
* namespace: `ckan-cloud`
* image: `minio/mc`
* command entrypoint: `/bin/sh -c 'while true; do sleep 86400; done'`

Add a `deis` minio host:

```
OLD_MINIO_CREDS=$(KUBECONFIG=$DEIS_KUBECONFIG kubectl -n deis get secret minio-user -o yaml | python3 -c "import sys, yaml, base64; data={k: base64.b64decode(v).decode() for k,v in yaml.load(sys.stdin)['data'].items() if k in ['accesskey','secretkey']}; print('{accesskey} {secretkey}'.format(**data))")
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc mc config host add deis https://old.minio.server/ $OLD_MINIO_CREDS
```

Add `prod` minio host:

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc config host add prod `ckan-cloud-operator storage credentials --raw`
```

Create the prod ckan bucket

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc mb prod/ckan
```

Copy the bucket policy from deis

```
ckan-cloud-operator ckan storage deis-minio-bucket-policy \
    | ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
        "sh -c 'cat > deis-minio-bucket-policy.json'"
```

Apply the policy to the bucket

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc policy deis-minio-bucket-policy.json prod/ckan
```


## Instance migration

### Preflight check

Verify DEIS_KUBECONFIG is connected to the deis cluster:

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl get nodes
```

Verify DB_OPERATIONS_POD is running

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup get pod $DB_OPERATIONS_POD
```

Login to gcloud on db operations pod (usually, should only be done once):

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec -it $DB_OPERATIONS_POD -c db -- bash -l
```

Verify ckan-cloud-operator is connected to the right cluster:

```
ckan-cloud-operator cluster info
```


### Get instance details

Set the old site id (instance id from old cluster):

```
OLD_SITE_ID=
```

Get some env vars and save in a file:

```
OLD_POD_NAME=`KUBECONFIG=$DEIS_KUBECONFIG kubectl -n $OLD_SITE_ID get pods -ocustom-columns=name:.metadata.name --no-headers`
OLD_DB_URL=$(KUBECONFIG=$DEIS_KUBECONFIG kubectl -n $OLD_SITE_ID exec $OLD_POD_NAME -- bash -c 'echo $CKAN_SQLALCHEMY_URL')
OLD_DATASTORE_URL=$(KUBECONFIG=$DEIS_KUBECONFIG kubectl -n $OLD_SITE_ID exec $OLD_POD_NAME -- bash -c 'echo $CKAN__DATASTORE__WRITE_URL')
OLD_STORAGE_PATH=$(KUBECONFIG=$DEIS_KUBECONFIG kubectl -n $OLD_SITE_ID exec $OLD_POD_NAME -- bash -c 'echo $CKANEXT__S3FILESTORE__AWS_STORAGE_PATH')
INSTANCE_MIGRATION_ENV=/etc/ckan-cloud/migration-${OLD_SITE_ID}.env
echo "
DB_OPERATIONS_POD=$DB_OPERATIONS_POD
DEIS_KUBECONFIG=$DEIS_KUBECONFIG
OLD_POD_NAME=$OLD_POD_NAME
OLD_SITE_ID=$OLD_SITE_ID
OLD_DB_URL=$OLD_DB_URL
OLD_DATASTORE_URL=$OLD_DATASTORE_URL
OLD_STORAGE_PATH=$OLD_STORAGE_PATH
" > $INSTANCE_MIGRATION_ENV
```

Verify

```
cat $INSTANCE_MIGRATION_ENV
```

### Place old instance in maintenance mode

Using Rancher - move the instance namespace to the migrated-instances project

Edit the instance's service and add `--migrated` suffix to the app label selector

Instance will now show "service unavailable"

Pause the deployment to prevent any changes but keep the pod running until migration is complete


### Migrate

Source the .env file and verify migrated instance

```
source `echo $INSTANCE_MIGRATION_ENV | tee /dev/stderr` && printf "\n\nMigrating from old site id: $OLD_SITE_ID\n\n"
```

Initialize the GitLab project for the instance:

```
ckan-cloud-operator initialize-gitlab viderum/cloud-${OLD_SITE_ID} --wait-ready
```

Make sure docker image was built, if it's not, check the error and modify Dockerfile accordingly

For some instances pip needs to be upgraded by adding `pip install --upgrade pip`

Dump the DBs

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec $DB_OPERATIONS_POD -c db -- bash -c \
    "source /root/google-cloud-sdk/completion.bash.inc
     source /root/google-cloud-sdk/path.bash.inc
     source functions.sh
     (
     dump_dbs $OLD_SITE_ID $OLD_DB_URL $OLD_DATASTORE_URL &&\
     upload_db_dumps_to_storage $OLD_SITE_ID &&\
     rm ${OLD_SITE_ID}*.sql &&\
     echo Successfully migrated $OLD_SITE_ID
     ) 2>/dev/stdout | tee -a ${OLD_SITE_ID}.logs
     "
```

Sometimes the exec session is dropped without completion, in that case you can continue to follow the logs and progress:

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec $DB_OPERATIONS_POD -c db -it -- bash -c 'ls -lah *.sql' &&\
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec $DB_OPERATIONS_POD -c db -it -- cat ${OLD_SITE_ID}.logs
```

Once complete, the output should contain the Google Storage urls, you can verify backup size using `gsutil ls -l URL`

check the import urls which will be used by the migration for the instance:

```
gsutil ls -l `ckan-cloud-operator ckan db-migration-import-urls $OLD_SITE_ID --raw`
```

Mirror the storage

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc mirror --overwrite -a deis/ckan/$OLD_STORAGE_PATH prod/ckan/$OLD_STORAGE_PATH
```

Migrate DBs

```
ckan-cloud-operator ckan migrate-deis-dbs $OLD_SITE_ID
```

Migrate the instance without db proxy

```
ckan-cloud-operator ckan migrate-deis-instance $OLD_SITE_ID --skip-gitlab --no-db-proxy --rerun
```

### Troubleshooting migrations


**General**

You can run each part of above migration script separately, check the CLI help mesages for possible flags and options

Enable debug / verbose debug output:

`export CKAN_CLOUD_OPERATOR_DEBUG=y`
`export CKAN_CLOUD_OPERATOR_DEBUG_VERBOSE=y`


**DB Dump**

The DB dumps might throw some errors but that doesn't mean it didn't work properly.

To debug these problems, execute bash on the db operations pod and run the relevant pg_dump commands manually (see functions.sh)

If you get permission errors, try to import using postgres user by modifying the OLD_DB_URL and OLD_DATASTORE_URL

You can get the postgres credentials from the db-operations pod:

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec $DB_OPERATIONS_POD -c db -it -- bash -c 'echo $PG_USERNAME:$PG_PASSWORD'
```


**DB Migration**

following might work for some failures to rerun from last successfull step:

```
ckan-cloud-operator ckan migrate-deis-dbs $OLD_SITE_ID --rerun
```

If that doesn't work, first, make sure there isn't a running instance for the site:

```
ckan-cloud-operator deis-instance delete $OLD_SITE_ID --force
```

Force full recreation of the migration and the DBs:

```
ckan-cloud-operator ckan migrate-deis-dbs $OLD_SITE_ID --force --recreate-dbs
```

If migration reported failure but you solved it manually and want to proceed anyway -

Edit the migration and set spec.imported-data: true

```
ckan-cloud-operator kubectl edit \
    `ckan-cloud-operator kubectl -- get ckanclouddbmigration -l ckan-cloud/old-site-id=$OLD_SITE_ID -oname`
```

Now you can continue with instance migration


**Instance Migration**

If instance migration fails or when making changes, you can rerun `ckan-cloud-operator ckan migrate-deis-instance` with following flags:

* `--recreate` - delete instance and DBs and recreate from scratch
* `--rerun` - re-run the migration, but doesn't re-migrate DBs and skips some components if already exist
* `--recreate-instance` - delete and re-create the instance (but not the DBs)

Skip specific parts of the migration:

* `--skip-gitlab`
* `--skip-routes`
* `--skip-solr`
* `--skip-deployment`


### Test and set routing

Get the CKAN admin credentails:

```
ckan-cloud-operator ckan admin-credentials $OLD_SITE_ID
```

Test the instance on the default instance route

Remove the instance site url override (or set to the desired external domain):

```
ckan-cloud-operator deis-instance edit $OLD_SITE_ID
```

some newer CKAN 2.8 instances require a direct connection to the DB, other instances should work using the db proxy:

* Delete the existing deployment: `ckan-cloud-operator kubectl -- -n $OLD_SITE_ID delete deployment $OLD_SITE_ID --force --now`
* Edit the instance and remove the no-db-proxy: true attribute: `ckan-cloud-operator deis-instance edit $OLD_SITE_ID`


#### For domains under the default root domain

For staging / testing instances, you can add additional subdomains under the default root domain.

First, set a CNAME for the subdomain to point to the default instance domain

Edit the relevant deis instance route and set extra-no-dns-subdomains to the default route:

```
ckan-cloud-operator routers get-routes --deis-instance-id $OLD_SITE_ID --edit
```

```
spec:
  extra-no-dns-subdomains:
  - OLD_SITE_ID
```

Wait a minute for DNS to propogate

Update the instances-default router for the change to take effect

```
ckan-cloud-operator routers update instances-default --wait-ready
```


#### For external domains

External domains need to use a dedicated load balancer which authenticates SSL certificates using http.

```
EXTERNAL_SUB_DOMAIN=
EXTERNAL_ROOT_DOMAIN=
```

Get the domain of the external domains router:

```
ckan-cloud-operator routers get prod-1 --dns
```

Set a CNAME or A record and wait a minute for DNS to propogate

You can verify using:

```
nslookup "${EXTERNAL_SUB_DOMAIN}.${EXTERNAL_ROOT_DOMAIN}" 1.1.1.1
```

Create a subdomain route to the deis instance:

```
ckan-cloud-operator routers create-deis-instance-subdomain-route prod-1 $OLD_SITE_ID $EXTERNAL_SUB_DOMAIN $EXTERNAL_ROOT_DOMAIN --wait-ready
```


## Stop old instance

Using Rancher, under migrated instances project - set the instance's deployment replicas to 0



## Bulk DB dumps

Following should run on edge / testing environments to bulk dump DBs

Run the following to create a script that dumps all db instances based on deis config yamls:

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

Login to the db operations pod, follow the intertactive gcloud initialization and paste the script:

```
KUBECONFIG=$DEIS_KUBECONFIG kubectl -n backup exec -it $DB_OPERATIONS_POD -c db -- bash -l
```


## Bulk storage sync

Following should run on edge / testing environments to sync all storage buckets continuously

```
ckan-cloud-operator kubectl -- exec -it deployment-pod::minio-mc -- \
    mc mirror --overwrite --watch -a deis/ckan edge/ckan
```
