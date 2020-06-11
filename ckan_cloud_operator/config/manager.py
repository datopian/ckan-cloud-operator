import base64
import os
import yaml
from sys import stdout

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.labels import manager as labels_manager


__CACHED_VALUES = {}


def get(key=None, default=None, secret_name=None, configmap_name=None, namespace=None, required=False, template=None):
    cache_key = _get_cache_key(secret_name, configmap_name, namespace)
    if cache_key not in __CACHED_VALUES:
        __CACHED_VALUES[cache_key] = _fetch(cache_key)
    if key:
        value = __CACHED_VALUES[cache_key].get(key, default)
    else:
        value = __CACHED_VALUES[cache_key]
    assert value or not required, f'config value is required for {cache_key}:{key}'
    if template:
        if key:
            return template.format(**{key: value})
        else:
            return template.format(**value)
    else:
        return value


def set(key=None, value=None, values=None, secret_name=None, configmap_name=None, namespace=None, extra_operator_labels=None,
        from_file=False, dry_run=False):
    log_kwargs = {'func': 'config/set', 'secret': secret_name, 'configmap': configmap_name, 'namespace': namespace}
    cache_key = _get_cache_key(secret_name, configmap_name, namespace)
    if secret_name is None and configmap_name is None and namespace is None:
        # hack to set label-prefix to bootstrap the environment
        if key == 'label-prefix' and not values:
            label_prefix = value
        elif not key and 'label-prefix' in values:
            label_prefix = values['label-prefix']
        else:
            label_prefix = None
        if label_prefix:
            __CACHED_VALUES.setdefault(cache_key, {})['label-prefix'] = label_prefix
    logs.debug('start', **log_kwargs)
    if from_file:
        assert key and value and not values
        with open(value) as f:
            value = f.read()
        values = {key: value}
    elif key or value:
        assert key and value and not values, 'Invalid arguments: must specify both key and value args and not specify values arg'
        values = {key: value}
    assert values, 'Invalid arguments: no values to save'
    return _save(cache_key, values, extra_operator_labels, dry_run=dry_run)


def delete_key(key, secret_name=None, namespace=None):
    kubectl.apply({
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': secret_name,
            'namespace': namespace
        },
        'type': 'Opaque',
        'data': {
            k: base64.b64encode(v.encode()).decode()
            for k, v
            in kubectl.decode_secret(kubectl.get('secret', secret_name, namespace=namespace)).items()
            if k != key and v
        }
    })


def delete(secret_name=None, configmap_name=None, namespace=None, exists_ok=False):
    cache_key = _get_cache_key(secret_name, configmap_name, namespace)
    _delete(cache_key, exists_ok)


def delete_by_extra_operator_labels(extra_operator_labels):
    labels = labels_manager.get_resource_labels(extra_operator_labels)
    labels_manager.delete_by_labels(labels, kinds=['configmap', 'secret'])


def list_configs(namespace=None, full=False, show_secrets=False):
    label_prefix = labels_manager.get_label_prefix()
    if not namespace: namespace = cluster_manager.get_operator_namespace_name()
    what = 'configmaps'
    if show_secrets:
        what += ',secrets'
    configs = kubectl.get(what, '-l', f'{label_prefix}/operator-config-namespace={namespace}', required=False)
    if configs:
        for config in configs.get('items', []):
            kind = config['kind']
            name = config.get('metadata', {}).get('name')
            data = {'kind': config['kind'],
                    'name': config.get('metadata', {}).get('name')}
            if full:
                if name:
                    data['values'] = get(
                        secret_name=name if kind == 'Secret' else None,
                        configmap_name=name if kind == 'ConfigMap' else None,
                        namespace=namespace,
                        required=False
                    )
                else:
                    data['values'] = None
            yield data

def get_preset_answer(namespace, configmap_name, secret_name, key, default=None):
    interactive_file = os.environ.get('CCO_INTERACTIVE_CI')
    if not interactive_file:
        return
    answers = yaml.load(open(interactive_file))
    section = '?'
    subsection = '?'
    namespace = namespace or 'default'
    try:
        if configmap_name:
            section = 'config'
            subsection = configmap_name
        else:
            section = 'secrets'
            subsection = secret_name
        return answers[namespace][section][subsection][key]
    except:
        if default is not None:
            return default
        logs.error(f'Failed to find in interactive file value for {namespace}.{section}.{subsection}.{key}')
        raise


def interactive_set(default_values, secret_name=None, configmap_name=None, namespace=None, from_file=False,
                    extra_operator_labels=None, interactive=True):
    log_kwargs = {'func': 'config/interactive_set', 'secret': secret_name, 'configmap': configmap_name, 'namespace': namespace}
    logs.debug('start', **log_kwargs)
    set_values = {}
    for key, default_value in default_values.items():
        saved_value = get(key, secret_name=secret_name, configmap_name=configmap_name, namespace=namespace)
        preset_value = get_preset_answer(namespace, configmap_name, secret_name, key, default=default_value)
        if preset_value:
            set_values[key] = preset_value
        elif interactive and stdout.isatty():
            if saved_value:
                if from_file:
                    msg = ', leave empty to use the saved value'
                else:
                    msg = f', leave empty to use the saved value: {saved_value}'
                    default_value = saved_value
            elif default_value is not None:
                assert not from_file
                msg = f', leave empty to use the default value: {default_value}'
            else:
                msg = ' (required)'
            if from_file:
                print(f'Enter the path to a file containing the value for {key}{msg}')
                source_path = input(f'{key} path: ')
                if source_path:
                    with open(source_path) as f:
                        set_values[key] = f.read()
                elif saved_value:
                    set_values[key] = saved_value
                else:
                    raise Exception('file path is required')
            else:
                if default_value in [True, False]:
                    print(f'Enter a boolean value for {key}{msg}')
                    entered_value = input(f'{key} [y/n]: ')
                    bool_value = default_value if entered_value == '' else (entered_value == 'y')
                    set_values[key] = 'y' if bool_value else 'n'
                else:
                    print(f'Enter a value for {key}{msg}')
                    entered_value = input(f'{key}: ')
                    set_values[key] = str(entered_value or default_value)
        else:
            set_values[key] = saved_value if saved_value is not None else default_value
    logs.debug('set', **log_kwargs)
    return set(values=set_values, secret_name=secret_name, configmap_name=configmap_name, namespace=namespace, extra_operator_labels=extra_operator_labels)


def _fetch(cache_key):
    config_type, namespace, config_name = _parse_cache_key(cache_key)
    fetch_func = {
        'secret': lambda: _fetch_secret(config_name, namespace),
        'configmap': lambda: _fetch_configmap(config_name, namespace)
    }.get(config_type)
    assert fetch_func, f'Invalid config type: {config_type}'
    return fetch_func() or {}


def _fetch_secret(secret_name, namespace):
    secret = kubectl.get(f'secret {secret_name}', required=False, namespace=namespace)
    return kubectl.decode_secret(secret) if secret else None


def _fetch_configmap(configmap_name, namespace):
    configmap = kubectl.get(f'configmap {configmap_name}', required=False, namespace=namespace)
    return configmap['data'] if configmap else None


def _save(cache_key, values, extra_operator_labels, dry_run=False):
    config_type, namespace, config_name = _parse_cache_key(cache_key)
    save_func = {
        'secret': lambda: _save_secret(values, config_name, namespace, extra_operator_labels, dry_run=dry_run),
        'configmap': lambda: _save_configmap(values, config_name, namespace, extra_operator_labels, dry_run=dry_run),
    }.get(config_type)
    assert save_func, f'Invalid config type: {config_type}'
    __CACHED_VALUES[cache_key] = res = save_func()
    return res


def _save_secret(values, secret_name, namespace, extra_operator_labels, dry_run=False):
    return kubectl.update_secret(
        secret_name,
        values,
        namespace=namespace,
        labels=_get_labels(secret_name=secret_name, namespace=namespace, extra_operator_labels=extra_operator_labels),
        dry_run=dry_run
    )


def _save_configmap(values, configmap_name, namespace, extra_operator_labels, dry_run=False):
    return kubectl.update_configmap(
        configmap_name, values, namespace=namespace,
        labels=_get_labels(configmap_name=configmap_name, namespace=namespace, extra_operator_labels=extra_operator_labels),
        dry_run=dry_run
    )


def _delete(cache_key, exists_ok=False):
    config_type, namespace, config_name = _parse_cache_key(cache_key)
    assert config_type in ['configmap', 'secret'], f'Invalid config type: {config_type}'
    ignore_not_found = ' --ignore-not-found' if exists_ok else ''
    kubectl.check_call(f'delete{ignore_not_found} {config_type} {config_name}')


def _get_labels(cache_key=None, secret_name=None, configmap_name=None, namespace=None, extra_operator_labels=None):
    if cache_key:
        assert not secret_name and not configmap_name and not namespace
    else:
        cache_key = _get_cache_key(secret_name, configmap_name, namespace)
    config_type, namespace, config_name = _parse_cache_key(cache_key)
    operator_labels = {
        f'operator-config-{config_type}': config_name,
        'operator-config-namespace': namespace
    }
    if extra_operator_labels:
        operator_labels.update(**extra_operator_labels)
    return labels_manager.get_resource_labels(operator_labels)


def _get_cache_key(secret_name, configmap_name, namespace):
    if secret_name:
        assert not configmap_name, f'Invalid arguments: cannot specify both secret_name and configmap_name: {secret_name}, {configmap_name}'
    configmap_name, namespace = cluster_manager.get_operator_configmap_namespace_defaults(configmap_name, namespace)
    return f'secret:{namespace}:{secret_name}' if secret_name else f'configmap:{namespace}:{configmap_name}'


def _parse_cache_key(cache_key):
    config_type, namespace, config_name = cache_key.split(':')
    return config_type, namespace, config_name
