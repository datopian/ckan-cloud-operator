from ckan_cloud_operator.config.manager import set_configmap_values


def set_provider(submodule, provider_id):
    set_configmap_values({f'{submodule}-provider-id': provider_id})
