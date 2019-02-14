from ckan_cloud_operator.providers import manager as providers_manager
from .minio.constants import PROVIDER_ID as minio_provider_id
from .constants import PROVIDER_SUBMODULE


def initialize(interactive=False):
    get_provider(default=minio_provider_id).initialize(interactive=interactive)


def get_provider(default=None):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default)


def deploy():
    get_provider().deploy()


def print_credentials():
    return get_provider().print_credentials()
