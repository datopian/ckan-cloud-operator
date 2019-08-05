import subprocess
import json
import yaml

from ckan_cloud_operator import logs


class DeisCkanInstanceSolr(object):

    def __init__(self, instance):
        self.instance = instance
        self.solr_spec = self.instance.spec.solrCloudCollection

    def update(self):
        self.instance.annotations.update_status('solr', 'created', lambda: self._update(), force_update=True)

    def delete(self):
        collection_name = self.solr_spec['name']
        logs.warning(f'Not deleting solrcloud collection {collection_name}')
        # from ckan_cloud_operator.providers.solr import manager as solr_manager
        # solr_manager.delete_collection(collection_name)

    def get_replication_factor(self):
        from ckan_cloud_operator.providers.solr import manager as solr_manager
        return solr_manager.get_replication_factor()

    def get_num_shards(self):
        from ckan_cloud_operator.providers.solr import manager as solr_manager
        return solr_manager.get_num_shards()

    def get(self):
        from ckan_cloud_operator.providers.solr import manager as solr_manager
        collection_name = self.instance.spec.solrCloudCollection['name']
        return solr_manager.get_collection_status(collection_name)

    def is_ready(self):
        return self.get().get('ready')

    def _update(self):
        status = self.get()
        if status['ready']:
            schema_name = status['schemaName']
            schema_version = status['schemaVersion']
            logs.info(f'Using existing solr schema: {schema_name} {schema_version}')
        elif 'configName' in self.solr_spec:
            config_name = self.solr_spec['configName']
            from ckan_cloud_operator.providers.solr import manager as solr_manager
            solr_manager.create_collection(status['collection_name'], config_name)
        else:
            raise NotImplementedError(f'Unsupported solr cloud collection spec: {self.solr_spec}')
