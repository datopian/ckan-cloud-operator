# Instance Management


## Reindex solr search index

Run a full re-indexing (might take a while if there are a lot of documents):

```
ckan-cloud-operator deis-instance ckan paster <INSTANCE_ID> search-index rebuild
```

See search-index help message for some additional reindexing options:

```
ckan-cloud-operator deis-instance ckan paster <INSTANCE_ID> search-index --help
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

