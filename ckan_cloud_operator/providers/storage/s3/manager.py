import json

from ckan_cloud_operator import logs, kubectl
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.cluster.manager import _generate_password
from ckan_cloud_operator.providers.cluster.aws.manager import aws_check_output, get_aws_credentials, _config_get as aws_config_get

from ..constants import CONFIG_NAME
from .constants import PROVIDER_ID


def initialize(interactive=False, storage_suffix='', use_existing_disk_name=False, dry_run=False):
    default_zone = aws_config_get('aws-default-region', is_secret=True)
    assert default_zone, 'No cluster region specified.'

    if interactive and not dry_run:
        config_manager.interactive_set(
            {'storage-region': default_zone},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        config_manager.interactive_set(
            {'aws-storage-access-key': None},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        config_manager.interactive_set(
            {'aws-storage-access-secret': None},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )


def create_bucket(instance_id, region=None, exists_ok=False, dry_run=False):
    if not region:
        region = config_manager.get('storage-region') or get_aws_credentials().get('region')

    assert region, 'No default region set for the cluster'

    bucket_exists = instance_id in list_s3_buckets(names_only=True)
    if not exists_ok and bucket_exists:
        raise Exception('Bucket for this instance already exists')

    bucket_name = '{}-cc{}'.format(instance_id, _generate_password(12))

    if not dry_run and not bucket_exists:
        aws_check_output(f's3 mb s3://{bucket_name} --region {region}')

    return {
        'BUCKET_NAME': f's3://{bucket_name}',
        'BUCKET_ACCESS_KEY': config_manager.get('aws-storage-access-key', secret_name=CONFIG_NAME),
        'BUCKET_ACCESS_SECRET': config_manager.get('aws-storage-access-secret', secret_name=CONFIG_NAME)
    }
    

def delete_bucket(instance_id, dry_run=False):
    s3_buckets = list(filter(lambda x: x.startswith(f'{instance_id}-cc'), list_s3_buckets(names_only=True)))
    if not s3_buckets:
        logs.warning(f'No bucket found for the instance "{instance_id}". Skipping.')
        return

    instance = kubectl.get(f'ckancloudckaninstance {instance_id}')
    bucket = instance['spec'].get('ckanStorageBucket').get(PROVIDER_ID)
    if not bucket:
        logs.warning('This instance does not have S3 bucket attached.')
        return

    bucket_name = bucket.get('BUCKET_NAME')

    cmd = f's3 rm {bucket_name} --recursive'
    if dry_run:
        cmd += ' --dryrun'

    # Two steps deletion. See the `aws s3 rb help`
    aws_check_output(cmd)
    if not dry_run:
        aws_check_output(f's3 rb {bucket_name}')


def get_bucket(instance_id):
    s3_buckets = list(filter(lambda x: x.startswith(f'{instance_id}-cc'), list_s3_buckets(names_only=True)))
    if not s3_buckets:
        logs.warning(f'No bucket found for the instance "{instance_id}" on S3. Skipping.')
        return

    instance = kubectl.get(f'ckancloudckaninstance {instance_id}')
    bucket = instance['spec'].get('ckanStorageBucket').get(PROVIDER_ID)
    if not bucket:
        logs.warning('This instance does not have S3 bucket attached.')
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


def list_s3_buckets(names_only=False):
    """Returns list of buckets on S3"""
    data = aws_check_output('s3 ls').decode()

    result = []
    for line in data.split('\n'):
        if not line.strip():
            continue

        timestamp, name = line.rsplit(maxsplit=1)
        if names_only:
            result.append(name)
        else:
            result.append([timestamp, name])

    return result
