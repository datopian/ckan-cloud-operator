from ckan_cloud_operator import gcloud


class DeisCkanInstanceStorage(object):

    def __init__(self, instance):
        self.instance = instance
        self.storage_spec = self.instance.spec.storage
        self.storage_path = self.storage_spec['path']

    def update(self):
        self.instance.annotations.update_status('storage', 'created', lambda: self._update(), force_update=True)

    def delete(self):
        print('WARNING! Storage was not deleted')

    def get(self):
        storage_path = self.storage_spec['path']
        # Some of the srotages are not named after instance, but {instance}-prod/stage etc..
        prod_paths = [storage_path, f'{storage_path}-prod', f'{storage_path}-production']
        staging_paths = [storage_path, f'{storage_path}-stage', f'{storage_path}-staging']
        storage_bucket = self.instance.ckan_infra.GCLOUD_STORAGE_BUCKET
        for p_path, s_path in zip(prod_paths, staging_paths):
            storage_path_ = s_path if 'stage' in 'storage_path' else p_path
            returncode, output = gcloud.getstatusoutput(f'ls gs://{storage_bucket}{storage_path_}',
                                                        gsutil=True,
                                                        ckan_infra=self.instance.ckan_infra)
            if returncode == 0:
                break
        if returncode == 0:
            return {'ready': True, 'path': storage_path, 'bucket': storage_bucket,
                    'root_paths': [l.strip() for l in output.split('\n')]}
        else:
            return {'ready': False, 'path': storage_path, 'bucket': storage_bucket,
                    'error': output}

    def _update(self):
        data = self.get()
        ready, storage_path, storage_bucket = data['ready'], data['path'], data['bucket']
        if not ready:
            print(f'Initializing storage: gs://{storage_bucket}{storage_path}')
            raise NotImplementedError('Storage initialization for new instances is not supported yet')
