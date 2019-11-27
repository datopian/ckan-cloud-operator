from ckan_cloud_operator.providers import manager as providers_manager
from .minio.constants import PROVIDER_ID as minio_provider_id
from .constants import PROVIDER_SUBMODULE


def initialize(interactive=False, provider_id=None, storage_suffix=None, use_existing_disk_name=None, dry_run=False):
    provider = get_provider(
        default=None,
        provider_id=provider_id,
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
