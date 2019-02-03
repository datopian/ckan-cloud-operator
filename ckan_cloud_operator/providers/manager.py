from ckan_cloud_operator.config.manager import get_cached_configmap_value

from ckan_cloud_operator.providers.db_proxy.constants import PROVIDER_SUBMODULE as db_proxy_provider_submodule
from ckan_cloud_operator.providers.db_proxy.pgbouncer.constants import PROVIDER_ID as pgbouncer_provider_id
from ckan_cloud_operator.providers.db_proxy.pgbouncer import manager as pgbouncer_manager

from ckan_cloud_operator.providers.db.constants import PROVIDER_SUBMODULE as db_provider_submodule
from ckan_cloud_operator.providers.db.gcloudsql.constants import PROVIDER_ID as gcloudsql_provider_id
from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager


def get_provider(submodule, required=True):
    provider_id = get_cached_configmap_value(f'{submodule}-provider-id')
    if not provider_id:
        if required:
            raise Exception(f'No provider found for {submodule}')
        else:
            return None
    elif submodule == db_proxy_provider_submodule:
        if provider_id == pgbouncer_provider_id:
            return pgbouncer_manager
        else:
            raise Exception(f'Invalid provider for {db_proxy_provider_submodule}: {provider_id}')
    elif submodule == db_provider_submodule:
        if provider_id == gcloudsql_provider_id:
            return gcloudsql_manager
        else:
            raise Exception(f'Invalid provider  for {db_provider_submodule}: {provider_id}')
    else:
        raise Exception(f'Invalid submodule: {submodule}')
