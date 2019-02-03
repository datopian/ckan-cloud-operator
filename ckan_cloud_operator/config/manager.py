from ckan_cloud_operator import kubectl

from ckan_cloud_operator.cluster.constants import OPERATOR_NAMESPACE
from ckan_cloud_operator.config.constants import OPERATOR_CONFIGMAP


def get_cached_secret(secret_name, namespace=OPERATOR_NAMESPACE):
    return _get_cached(_get_secret_cache_key(secret_name, namespace))


def get_cached_configmap(configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    return _get_cached(_get_configmap_cache_key(configmap_name, namespace))


def get_cached_secret_value(secret_name, key, default=None, namespace=OPERATOR_NAMESPACE):
    return get_cached_secret(secret_name, namespace=namespace).get(key, default)


def get_cached_secret_values(secret_name, *keys, default=None, namespace=OPERATOR_NAMESPACE):
    configmap = get_cached_secret(secret_name, namespace=namespace)
    return [configmap.get(key, default) for key in keys]


def get_cached_configmap_value(key, default=None, configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    return get_cached_configmap(configmap_name, namespace=namespace).get(key, default)


def get_cached_configmap_values(*keys, default=None, configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    configmap = get_cached_configmap(configmap_name, namespace=namespace)
    return [configmap.get(key, default) for key in keys]


def get_secret(secret_name, namespace=OPERATOR_NAMESPACE):
    secret = kubectl.get(f'secret {secret_name}', required=False, namespace=namespace)
    if secret:
        return kubectl.decode_secret(secret)
    else:
        return {}


def get_configmap(configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    configmap = kubectl.get(f'configmap {configmap_name}', required=False, namespace=namespace)
    if configmap:
        return configmap['data']
    else:
        return {}


def set_secret_values(secret_name, values, namespace=OPERATOR_NAMESPACE):
    secret = get_secret(secret_name, namespace=namespace)
    secret.update(**values)
    kubectl.update_secret(secret_name, values, namespace=namespace, labels=get_secret_labels(secret_name, namespace=namespace))
    _reload_cache(_get_secret_cache_key(secret_name, namespace), secret)


def set_configmap_values(values, configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    configmap = get_configmap(configmap_name, namespace=namespace)
    configmap.update(**values)
    kubectl.apply(kubectl.get_configmap(
        configmap_name,
        get_configmap_labels(configmap_name, namespace),
        configmap,
        namespace
    ))
    _reload_cache(_get_configmap_cache_key(configmap_name, namespace), configmap)


def get_secret_labels(secret_name, namespace=OPERATOR_NAMESPACE):
    label_prefix = get_label_prefix()
    return {
        f'{label_prefix}/operator-secret-name': secret_name,
        f'{label_prefix}/operator-secret-namespace': namespace
    }


def get_configmap_labels(configmap_name=OPERATOR_CONFIGMAP, namespace=OPERATOR_NAMESPACE):
    label_prefix = get_label_prefix()
    return {
        f'{label_prefix}/operator-secret-name': configmap_name,
        f'{label_prefix}/operator-secret-namespace': namespace
    }


def get_label_prefix():
    return 'ckan-cloud'


__CACHED_VALUES = {}


def _get_secret_cache_key(secret_name, namespace):
    assert ':' not in secret_name and ':' not in namespace
    return f'secret:{namespace}:{secret_name}'


def _get_configmap_cache_key(configmap_name, namespace):
    assert ':' not in configmap_name and ':' not in namespace
    return f'configmap:{namespace}:{configmap_name}'


def _get_cached(cache_key):
    if cache_key not in __CACHED_VALUES or __CACHED_VALUES[cache_key]['__need_to_fetch__']:
        __CACHED_VALUES[cache_key] = {}
        config_type, namespace, config_name = cache_key.split(':')
        if config_type == 'secret':
            values = get_secret(config_name, namespace=namespace)
        elif config_type == 'configmap':
            values = get_configmap(config_name, namespace=namespace)
        else:
            raise Exception(f'Invalid config type: {config_type}')
        __CACHED_VALUES[cache_key].update(**values)
        __CACHED_VALUES[cache_key]['__need_to_fetch__'] = False
    return {k: v for k, v in __CACHED_VALUES[cache_key].items() if k != '__need_to_fetch__'}


def _reload_cache(cache_key, values=None):
    if values:
        __CACHED_VALUES[cache_key] = {'__need_to_fetch__': False}
        __CACHED_VALUES[cache_key].update(**values)
    else:
        if cache_key in __CACHED_VALUES:
            __CACHED_VALUES[cache_key]['__need_to_fetch__'] = True
        _get_cached(cache_key)
