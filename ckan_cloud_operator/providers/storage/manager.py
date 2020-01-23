from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator import logs

from .minio.constants import PROVIDER_ID as minio_provider_id
from .s3.constants import PROVIDER_ID as s3_provider_id
from .constants import PROVIDER_SUBMODULE, CONFIG_NAME


def initialize(interactive=False, provider_id=None, storage_suffix=None, use_existing_disk_name=None, dry_run=False):
    if not provider_id and interactive:
        config_manager.interactive_set(
            {'use-cloud-native-storage': True},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        if config_manager.get('use-cloud-native-storage', secret_name=CONFIG_NAME):
            provider_id = get_provider_id()

    logs.info(f'Storage init: chosen provider_id: {provider_id}')
    provider = get_provider(
        default=minio_provider_id,
        provider_id=provider_id
    ).initialize(
        interactive=interactive,
        storage_suffix=storage_suffix,
        use_existing_disk_name=use_existing_disk_name,
        dry_run=dry_run
    )
    if provider:
        provider.initialize(
            interactive=interactive,
            storage_suffix=storage_suffix,
            use_existing_disk_name=use_existing_disk_name,
            dry_run=dry_run
        )


def get_provider_id():
    from ckan_cloud_operator.providers.cluster import manager as cluster_manager
    from ckan_cloud_operator.providers.cluster.gcloud.constants import PROVIDER_ID as gcloud_provider_id
    from ckan_cloud_operator.providers.cluster.aws.constants import PROVIDER_ID as aws_provider_id
    from ckan_cloud_operator.providers.cluster.azure.constants import PROVIDER_ID as azure_provider_id
    from .s3.constants import PROVIDER_ID as s3_provider_id
    from .gcloud.constants import PROVIDER_ID as gcloud_storage_provider_id
    from .azure.constants import PROVIDER_ID as azure_storage_provider_id

    cluster_provider_id = cluster_manager.get_provider_id()
    if cluster_provider_id == gcloud_provider_id:
        return gcloud_storage_provider_id
    elif cluster_provider_id == aws_provider_id:
        return s3_provider_id
    elif cluster_provider_id == azure_provider_id:
        return azure_storage_provider_id
    return 'minio'


def get_provider(default=None, provider_id=None):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, provider_id=provider_id, required=False)


def print_credentials(raw=False, storage_suffix=None, provider_id=None):
    return get_provider(provider_id=provider_id).print_credentials(raw=raw, storage_suffix=storage_suffix)
