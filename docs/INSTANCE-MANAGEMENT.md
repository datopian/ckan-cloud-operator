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
