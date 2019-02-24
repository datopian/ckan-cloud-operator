class DeisCkanInstanceStorage(object):

    def __init__(self, instance):
        self.instance = instance
        self.storage_spec = self.instance.spec.storage
        self.storage_path = self.storage_spec['path']

    def update(self):
        assert self.get()['ready']

    def delete(self):
        print('WARNING! Storage was not deleted')

    def get(self):
        storage_path = self.storage_spec['path']
        from ckan_cloud_operator.providers.ckan.storage import manager as ckan_storage_manager
        return ckan_storage_manager.get_storage_path_status(storage_path)
