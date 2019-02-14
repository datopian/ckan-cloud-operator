from ckan_cloud_operator.providers import manager as providers_manager
from .constants import PROVIDER_SUBMODULE
from .pgbouncer.constants import PROVIDER_ID as pgbouncer_provider_id


def initialize():
    get_provider(default=pgbouncer_provider_id).initialize()


def start_port_forward():
    get_provider().start_port_forward()


def update(wait_updated=False):
    get_provider().update(wait_updated=wait_updated)


def reload():
    get_provider().reload()


def get_provider(default=None, required=True):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, required=required)
