from ckan_cloud_operator.providers import manager as providers_manager
from .constants import PROVIDER_SUBMODULE
from .adminer.constants import PROVIDER_ID as adminer_provider_id


def initialize():
    get_provider(default=adminer_provider_id).initialize()


def start():
    """Start a web-UI for db management"""
    get_provider().start()


def get_provider(default=None):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default)
