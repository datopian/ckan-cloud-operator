import subprocess
import yaml

from ckan_cloud_operator import logs

from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.infra import CkanInfra


def initialize(interactive=False):
    config_manager.interactive_set(
        {
            'default-storage-bucket': 'ckan',
        },
        secret_name='ckan-storage-config',
        interactive=interactive
    )
    logs.warning('Minio bucket policy was not applied!')


def get_deis_minio_bucket_policy():
    from ckan_cloud_operator.providers.ckan import manager as ckan_manager
    path_to_old_cluster_kubeconfig = ckan_manager.get_path_to_old_cluster_kubeconfig()
    return subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                   f'kubectl -n deis exec -it deis-minio-6ddd8f5d85-wphhb '
                                   f'-- cat /export/.minio.sys/buckets/ckan/policy.json',
                                   shell=True).decode()


def get_default_storage_bucket():
    return config_get('default-storage-bucket')


def config_get(key):
    return config_manager.get(key, secret_name='ckan-storage-config')


def get_storage_path_status(storage_path, storage_bucket=None):
    return {'ready': True, 'path': storage_path, 'bucket': storage_bucket or get_default_storage_bucket()}
    # if not storage_bucket: storage_bucket = get_default_storage_bucket()
    # Some of the srotages are not named after instance, but {instance}-prod/stage etc..
    # prod_paths = [storage_path, f'{storage_path}-prod', f'{storage_path}-production']
    # staging_paths = [storage_path, f'{storage_path}-stage', f'{storage_path}-staging']
    # returncode, output = None, None
    # for p_path, s_path in zip(prod_paths, staging_paths):
    #     storage_path_ = s_path if 'stage' in 'storage_path' else p_path
        # returncode, output = cluster_manager.get_provider().getstatusoutput(
        #     f'ls gs://{storage_bucket}{storage_path_}', gsutil=True
        # )
        # if returncode == 0:
        #     break
    # if returncode == 0:
    #     return {'ready': True, 'path': storage_path, 'bucket': storage_bucket,
    #             'root_paths': [l.strip() for l in output.split('\n')]}
    # else:
    #     return {'ready': False, 'path': storage_path, 'bucket': storage_bucket,
    #             'error': output}


def update(storage_path, storage_bucket=None):
    data = get_storage_path_status(storage_path, storage_bucket)
    ready, storage_path, storage_bucket = data['ready'], data['path'], data['bucket']
    if not ready:
        print(f'Initializing storage: gs://{storage_bucket}{storage_path}')
        raise NotImplementedError('Storage initialization for new instances is not supported yet')


def delete(storage_path, stoarge_bucket=None):
    print('WARNING! Storage was not deleted')
