import json
import re

from ckan_cloud_operator import logs, kubectl
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.cluster.gcloud.manager import _config_get as cluster_config_get, check_output as gcloud_check_output

from ..constants import CONFIG_NAME
from .constants import PROVIDER_ID


def initialize(interactive=False, storage_suffix='', use_existing_disk_name=False, dry_run=False):
    default_zone = cluster_config_get('cluster-compute-zone')
    assert default_zone, 'No cluster region specified.'

    if interactive and not dry_run:
        config_manager.interactive_set(
            {'storage-region': default_zone},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )


def create_bucket(instance_id, region=None, exists_ok=False, dry_run=False):
    if not region:
        region = cluster_config_get('cluster-compute-zone')

    assert region, 'No default region set for the cluster'

    bucket_exists = instance_id in list_gcloud_buckets()
    if not exists_ok and bucket_exists:
        raise Exception('Bucket for this instance already exists')

    if not dry_run and not bucket_exists:
        gcloud_check_output(f'mb gs://{instance_id} -l {region}', gsutil=True)

    return {
        'BUCKET_NAME': f'gs://{instance_id}'
    }
    

def delete_bucket(instance_id, dry_run=False):
    if instance_id not in list_gcloud_buckets():
        logs.warning(f'No bucket found for the instance "{instance_id}". Skipping.')
        return

    logs.info(f'Removing bucket for instance_id {instance_id}')
    if not dry_run:
        gcloud_check_output(f'rm -r gs://{instance_id}', gsutil=True)


def get_bucket(instance_id):
    if instance_id not in list_gcloud_buckets():
        logs.warning(f'No bucket found for the instance "{instance_id}" on Google Cloud. Skipping.')
        return

    instance = kubectl.get(f'ckancloudckaninstance {instance_id}')
    bucket = instance['spec'].get('ckanStorageBucket').get(PROVIDER_ID)
    if not bucket:
        logs.warning('This instance does not have Google Cloud bucket attached.')
        return

    return {
        'instance_id': instance_id,
        'ckanStorageBucket': bucket
    }


def list_buckets():
    """Returns list of buckets attached to CKAN Instances"""
    result = []
    for item in kubectl.get('ckancloudckaninstance').get('items', []):
        bucket = item['spec'].get('ckanStorageBucket', {}).get(PROVIDER_ID)
        if not bucket:
            continue
        result.append({
            'instance_id': item['spec']['id'],
            'ckanStorageBucket': bucket
        })

    return result


def list_gcloud_buckets():
    """Returns list of buckets on GCP"""
    data = gcloud_check_output('ls', gsutil=True).decode()

    result = []
    for line in data.split('\n'):
        if not line.strip():
            continue

        bucket_name = re.match(r'gs://([-_a-zA-Z0-9]+)/', line)
        if not bucket_name:
            continue

        result.append(bucket_name.group(1))

    return result
