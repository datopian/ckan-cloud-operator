# Infrastructure Management


## DB Instances

DB Instances are namespaced by an optional prefix

Initialize a new DB instance with given PREFIX:

```
ckan-cloud-operator db gcloudsql initialize --interactive --db-prefix PREFIX
```

To move an existing instance DB to a new instance, see [disaster recovery](/docs/DISASTER-RECOVERY.md), add `--db-prefix` argument to the create command.

When using a prefixed DB locally, ensure you start a proxy for this DB as well:

```
ckan-cloud-operator db proxy port-forward --db-prefix PREFIX
```


## DB Connection pooler - PgBouncer

```
psql -d `ckan-cloud-operator db connection-string --admin`
postgres=> \connect pgbouncer
pgbouncer=# show lists;
pgbouncer=# show pools;
pgbouncer=# show help;
```


## Load Balancers and routing

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


## Storage management

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
