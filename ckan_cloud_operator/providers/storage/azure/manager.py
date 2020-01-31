import json

from ckan_cloud_operator import logs, kubectl
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.cluster.azure.manager import _config_get as cluster_config_get, az_check_output

from ..constants import CONFIG_NAME
from .constants import PROVIDER_ID


def initialize(interactive=False, storage_suffix='', use_existing_disk_name=False, dry_run=False):
    default_zone = cluster_config_get('azure-default-location')
    assert default_zone, 'No cluster region specified.'
    if interactive and not dry_run:
        config_manager.interactive_set(
            {'storage-region': default_zone},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        config_manager.interactive_set(
            {'storage-account-name': ''},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        config_manager.interactive_set(
            {'storage-account-key': ''},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )


def _get_cred_options():
    account_name = config_manager.get('storage-account-name', secret_name=CONFIG_NAME)
    account_key = config_manager.get('storage-account-key', secret_name=CONFIG_NAME)
    return f'--account-name {account_name} --account-key {account_key}'


def create_bucket(instance_id, region=None, exists_ok=False, dry_run=False):
    if not region:
        region = cluster_config_get('azure-default-location')

    assert region, 'No default region set for the cluster'

    bucket_exists = instance_id in list_azure_buckets()
    if not exists_ok and bucket_exists:
        raise Exception('Bucket for this instance already exists')

    if not dry_run and not bucket_exists:
        cred_options = _get_cred_options()
        az_check_output(f'storage container create -n {instance_id} {cred_options}')

    return {
        'BUCKET_NAME': instance_id,
        'STORAGE_ACCOUNT_NAME': config_manager.get('storage-account-name', secret_name=CONFIG_NAME),
        'STORAGE_ACCOUNT_KEY': config_manager.get('storage-account-key', secret_name=CONFIG_NAME)
    }


def delete_bucket(instance_id, dry_run=False):
    if instance_id not in list_azure_buckets():
        logs.warning(f'No bucket found for the instance "{instance_id}". Skipping.')
        return

    if dry_run:
        return

    logs.info(f'Removing Azure storage bucket for instance_id {instance_id}')

    cred_options = _get_cred_options()
    az_check_output(f'storage container delete -n {instance_id} {cred_options}')


def get_bucket(instance_id):
    if instance_id not in list_azure_buckets():
        logs.warning(f'No bucket found for the instance "{instance_id}" in this Azure storage account. Skipping.')
        return

    instance = kubectl.get(f'ckancloudckaninstance {instance_id}')
    bucket = instance['spec'].get('bucket').get(PROVIDER_ID)
    if not bucket:
        logs.warning('This instance does not have Azure bucket attached.')
        return

    return {
        'instance_id': instance_id,
        'bucket': bucket
    }


def list_buckets():
    """Returns list of buckets attached to CKAN Instances"""
    result = []
    for item in kubectl.get('ckancloudckaninstance').get('items', []):
        bucket = item['spec'].get('bucket', {}).get(PROVIDER_ID)
        if not bucket:
            continue
        result.append({
            'instance_id': item['spec']['id'],
            'bucket': bucket
        })

    return result


def list_azure_buckets():
    """Returns list of containers on Azure storage account"""
    cred_options = _get_cred_options()
    data = json.loads(az_check_output(f'storage container list {cred_options}'))

    return [x['name'] for x in data]
