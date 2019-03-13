from ckan_cloud_operator.providers import manager as providers_manager
from .constants import PROVIDER_SUBMODULE
from .gcloudsql.constants import PROVIDER_ID as gcloudsql_provider_id


def initialize():
    get_provider(default=gcloudsql_provider_id).initialize()


def start_port_forward(db_prefix=None):
    get_provider().start_port_forward(db_prefix=db_prefix)


def update(wait_updated=False, set_pool_mode=None):
    get_provider().update(wait_updated=wait_updated, set_pool_mode=set_pool_mode)


def reload():
    get_provider().reload()


def get_provider(default=None, required=True):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, required=required)
