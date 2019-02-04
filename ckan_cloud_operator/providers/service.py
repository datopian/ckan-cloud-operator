from ckan_cloud_operator.config.manager import set_configmap_values
from ckan_cloud_operator.config.manager import get_cached_configmap_value


def set_provider(submodule, provider_id):
    set_configmap_values({f'{submodule}-provider-id': provider_id})


def get_provider_id(submodule, required=True):
    provider_id = get_cached_configmap_value(f'{submodule}-provider-id')
    assert provider_id or not required
    return provider_id
