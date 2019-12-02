from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers import manager as providers_manager

from .minio.constants import PROVIDER_ID as minio_provider_id
from .s3.constants import PROVIDER_ID as s3_provider_id
from .constants import PROVIDER_SUBMODULE, CONFIG_NAME


def initialize(interactive=False, provider_id=None, storage_suffix=None, use_existing_disk_name=None, dry_run=False):
    from ckan_cloud_operator.providers.cluster import manager as cluster_manager
    from ckan_cloud_operator.providers.cluster.gcloud.constants import PROVIDER_ID as gcloud_provider_id
    from ckan_cloud_operator.providers.cluster.aws.constants import PROVIDER_ID as aws_provider_id

    if not provider_id and interactive:
        cluster_provider_id = cluster_manager.get_provider_id()

        config_manager.interactive_set(
            {'use-cloud-native-storage': True},
            secret_name=CONFIG_NAME,
            interactive=interactive
        )
        if config_manager.get('use-cloud-native-storage', secret_name=CONFIG_NAME):
            default_zone = None
            if cluster_provider_id == gcloud_provider_id:
                from ckan_cloud_operator.providers.cluster.gcloud.manager import _config_get as gcloud_config_get

                default_zone = gcloud_config_get('cluster-compute-zone')
                provider_id = 'gcloud'

            elif cluster_provider_id == aws_provider_id:
                from ckan_cloud_operator.providers.cluster.aws.manager import _config_get as aws_config_get

                default_zone = aws_config_get('aws-default-region')
                provider_id = 's3'

            assert default_zone, 'No cluster region specified.'

            config_manager.interactive_set(
                {'storage-region': default_zone},
                secret_name=CONFIG_NAME,
                interactive=interactive
            )

    provider = get_provider(
        default=None,
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


def get_provider(default=None, provider_id=None):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, provider_id=provider_id, required=False)


def print_credentials(raw=False, storage_suffix=None, provider_id=None):
    return get_provider(provider_id=provider_id).print_credentials(raw=raw, storage_suffix=storage_suffix)
