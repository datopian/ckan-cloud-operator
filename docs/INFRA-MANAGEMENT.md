# Infrastructure Management


## DB Connection pooler - PgBouncer

```
psql -d `ckan-cloud-operator db connection-string --admin`
postgres=> \connect pgbouncer
pgbouncer=# show lists;
pgbouncer=# show pools;
pgbouncer=# show help;
```


## Load Balancers and routing

List routers:

```
ckan-cloud-operator routers list
```

List routers with full details including all related routes:

```
ckan-cloud-operator routers list --full
```

Get routes for an instance:

```
ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID
```

edit route specs:

```
EDITOR=nano ckan-cloud-operator routers get-routes --deis-instance-id INSTANCE_ID --edit
```

Create an external domains router which is backed by a dedicated load balancer:

```
ckan-cloud-operator routers create-traefik-router ROUTER_NAME --external-domains
```

Route an instance through this router for a specified external domain:

```
ckan-cloud-operator routers create-deis-instance-subdomain-route ROUTER_NAME DEIS_INSTANCE_ID SUB_DOMAIN ROOT_DOMAIN
```

Other type of routes can be created as well, see `ckan-cloud-operator routers --help`
