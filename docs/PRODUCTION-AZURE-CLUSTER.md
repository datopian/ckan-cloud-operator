# Creating a Production CKAN Cloud cluster using Azure Cloud Platform

## Prerequisites

* An Azure Portal account with admin privileges and matching access and secret keys.
* An existing AKS cluster
* An "Azure Database for PostgreSQL" server instance
* A CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

## Initialize the cluster
Run interactive initialization of the currently connected cluster:
```
ckan-cloud-operator cluster initialize --interactive
```

While interactive initialization:
- If environment is production, set `env-id` to `p` on "routers" step.
- On "solr" step of interactive initialization choose `self-hosted: y`


## Optional: install sample CKAN instance
TODO
