import hashlib

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.annotations import manager as annotations_manager


def initialize(log_kwargs=None):
    values = {
        'crd-group': 'stable.viderum.com',
        'crd-prefix': 'CkanCloud'
    }
    logs.info(f'Setting default crds module configurations', **(log_kwargs or {}), **values)
    config_manager.set(values=values)


def get_crd_group():
    return config_manager.get('crd-group')


def get_crd_prefix():
    return config_manager.get('crd-prefix')


def get(singular, *args, name=None, required=True, get_cmd='get', **kwargs):
    """Run kubectl.get for the given crd singular value and optional get args / kwargs"""
    crd_prefix = get_crd_prefix()
    _, kind_suffix = _get_plural_kind_suffix(singular)
    if name:
        args = [get_resource_name(singular, name), *args]
    return kubectl.get(f'{crd_prefix}{kind_suffix}', *args, required=required, get_cmd=get_cmd, **kwargs)


def edit(singular, *edit_args, name=None, **edit_kwargs):
    """Run kubectl.get for the given crd singular value and optional get args / kwargs"""
    crd_prefix = get_crd_prefix()
    _, kind_suffix = _get_plural_kind_suffix(singular)
    what = f'{crd_prefix}{kind_suffix}'
    if name:
        what += '/' + get_resource_name(singular, name)
    return kubectl.edit(what, *edit_args, **edit_kwargs)


def delete(singular, name):
    config_delete(singular, name, by_labels=True)
    crd_prefix = get_crd_prefix()
    _, kind_suffix = _get_plural_kind_suffix(singular)
    name = get_resource_name(singular, name)
    kubectl.check_call(f'delete --ignore-not-found {crd_prefix}{kind_suffix} {name}')


def install_crd(singular, plural_suffix, kind_suffix, hash_names=False):
    logs.info(f'Installing operator crd: {singular}, {plural_suffix}, {kind_suffix}')
    _set_plural_kind_suffix(singular, plural_suffix, kind_suffix, hash_names=hash_names)
    label_prefix = labels_manager.get_label_prefix().replace('-', '')
    kubectl.install_crd(
        f'{label_prefix}{plural_suffix}',
        f'{label_prefix}{singular}',
        get_resource_kind(singular)
    )


def list_crds(full=False, debug=False):
    for config_key in config_manager.get():
        if config_key.startswith('installed-crd-'):
            singular = config_key.replace('installed-crd-', '')
            yield get_crd(singular, full=full, debug=debug)


def get_crd(singular, full=True, debug=False):
    if debug: full = True
    plural_suffix, kind_suffix = _get_plural_kind_suffix(singular)
    label_prefix = labels_manager.get_label_prefix().replace('-', '')
    data = {'singular': f'{label_prefix}{singular}',
            'plural': f'{label_prefix}{plural_suffix}',
            'kind': get_resource_kind(singular),
            'singular-suffix': singular}
    if full:
        data['resources'] = []
        items = get(singular)
        if items:
            for resource in items.get('items', []):
                resource_data = {'name': resource.get('metadata', {}).get('name')}
                if debug:
                    resource_data['labels'] = resource.get('metadata', {}).get('labels')
                    resource_data['spec'] = resource.get('spec')
                data['resources'].append(resource_data)
    return data


def list_resources(singular=None, name=None):
    if singular:
        for item in get(singular).get('items', []):
            resource = {'name': item.get('metadata', {}).get('name')}
            yield resource
    else:
        for crd in list_crds(full=False, debug=False):
            for resource in list_resources(crd['singular-suffix'], name):
                resource['kind'] = crd['kind']
                yield resource


def get_resource(singular, name, extra_label_suffixes=None, **kwargs):
    crd_group = get_crd_group()
    _, kind_suffix = _get_plural_kind_suffix(singular)
    resource = kubectl.get_resource(
        f'{crd_group}/v1',
        get_resource_kind(singular),
        get_resource_name(singular, name),
        get_resource_labels(singular, name, extra_label_suffixes=extra_label_suffixes)
    )
    resource.update(**kwargs)
    return resource


def get_resource_name(singular, name, allow_hash_names=True):
    # print(f'get_resource_name: {singular} {name}')
    resource_name = labels_manager.get_resource_name(get_resource_suffix(singular, name))
    if _get_hash_names(singular) and allow_hash_names:
        resource_name = 'cc' + hashlib.blake2b(name.encode(), digest_size=16).hexdigest()
    # print(f'output resource name: {resource_name}')
    return resource_name


def get_resource_kind(singular):
    crd_prefix = get_crd_prefix()
    _, kind_suffix = _get_plural_kind_suffix(singular)
    return f'{crd_prefix}{kind_suffix}'


def get_resource_suffix(singular, name):
    parts = [singular]
    if name:
        parts.append(name)
    return '-'.join(parts)


def get_resource_labels(singular, name, extra_label_suffixes=None, for_deployment=False):
    label_suffixes = {
        f'crd-{singular}-name': name,
    }
    if extra_label_suffixes:
        label_suffixes.update(**extra_label_suffixes)
    extra_labels = {'app': get_deployment_app_label(singular, name)} if for_deployment else {}
    return labels_manager.get_resource_labels(label_suffixes, extra_labels=extra_labels)


def get_deployment_app_label(singular, name):
    return get_resource_suffix(singular, name)


def get_resource_annotations(singular, name):
    return annotations_manager.get_global_annotations()


def config_set(singular, name, key=None, value=None, values=None, namespace=None, is_secret=False):
    """store key/values in a secret or configmap"""
    resource_name = get_resource_name(singular, name)
    config_manager.set(
        key=key,
        value=value,
        values=values,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        namespace=namespace,
        extra_operator_labels=_get_label_suffixes(singular, name)
    )


def config_get(singular, name, key=None, default=None, required=False, namespace=None, is_secret=False):
    resource_name = get_resource_name(singular, name)
    return config_manager.get(
        key=key,
        default=default,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        required=required,
        namespace=namespace
    )


def config_delete(singular, name, namespace=None, is_secret=False, exists_ok=False, by_labels=False):
    resource_name = get_resource_name(singular, name)
    if by_labels:
        config_manager.delete_by_extra_operator_labels(_get_label_suffixes(singular, name))
    else:
        config_manager.delete(
            secret_name=resource_name if is_secret else None,
            configmap_name=None if is_secret else resource_name,
            namespace=namespace,
            exists_ok=exists_ok
        )


def config_interactive_set(singular, name, default_values=None, namespace=None, is_secret=False, from_file=False):
    resource_name = get_resource_name(singular, name)
    config_manager.interactive_set(
        default_values,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        namespace=namespace,
        from_file=from_file
    )


def _get_plural_kind_suffix(singular):
    parts = config_manager.get(f'installed-crd-{singular}', required=True).split(',')
    plural_suffix = parts[0]
    kind_suffix = parts[1]
    return plural_suffix, kind_suffix


def _get_hash_names(singular):
    parts = config_manager.get(f'installed-crd-{singular}', required=True).split(',')
    return len(parts) > 2 and parts[2] == 'y'


def _set_plural_kind_suffix(singular, plural_suffix, kind_suffix, hash_names=False):
    hash_names = 'y' if hash_names else 'n'
    config_manager.set(f'installed-crd-{singular}', f'{plural_suffix},{kind_suffix},{hash_names}')


def _get_label_suffixes(singular, name):
    return {
        f'crd-{singular}-name': name,
        f'crd-singular': singular,
        f'crd-name': name,
    }
