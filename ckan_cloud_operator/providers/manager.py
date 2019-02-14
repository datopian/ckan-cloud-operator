from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.annotations import manager as annotations_manager


def get_provider(submodule, required=True, supported_provider_ids=None, default=None, verbose=False):
    if default: required = False
    provider_id = get_provider_id(submodule, required=required)
    if not provider_id:
        if default:
            provider_id = default
        else:
            return None
    if verbose:
        logs.info(f'submodule {submodule} using provider_id {provider_id}')
    if not supported_provider_ids or provider_id in supported_provider_ids:
        provider_manager = _get_submodule_ids_provider_or_provider_ids(submodule, provider_id)
    else:
        provider_manager = None
    if provider_manager:
        return provider_manager
    else:
        msg = f' (supported provider ids: {supported_provider_ids})' if supported_provider_ids else ''
        logs.critical(f'Invalid submodule / provider: {submodule} / {provider_id}{msg}')
        raise Exception('failed to get provider')


def get_providers(submodule, verbose=False):
    res = {
        provider_id: _get_submodule_ids_provider_or_provider_ids(submodule, provider_id)
        for provider_id in _get_submodule_ids_provider_or_provider_ids(submodule)
    }
    if verbose:
        provider_ids = list(res.keys())
        logs.info(f'Providers for submodule {submodule}: {provider_ids}')
    return res


def list_providers():
    res = {}
    for submodule in _get_submodule_ids_provider_or_provider_ids():
        res[submodule] = {
            'providers': _get_submodule_ids_provider_or_provider_ids(submodule),
            'selected-provider': get_provider_id(submodule, required=False)
        }
    return res


def set_provider(submodule, provider_id):
    config_manager.set(
        key=get_operator_configmap_key(submodule, suffix='main-provider-id'),
        value=provider_id
    )


def get_provider_id(submodule, required=True, default=None):
    if default: required = False
    return config_manager.get(
        get_operator_configmap_key(submodule, suffix='main-provider-id'),
        required=required,
        default=default
    )


def get_operator_configmap_key(submodule, provider_id=None, suffix=None):
    """Returns a key which can be used to store data for the given submodule/provider in the default operator configmap"""
    return get_resource_name(submodule, provider_id, suffix)


def config_set(submodule, provider_id=None, key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None):
    """store key/values in a secret or configmap"""
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    config_manager.set(
        key=key,
        value=value,
        values=values,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        namespace=namespace
    )


def config_get(submodule, provider_id=None, key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    return config_manager.get(
        key=key,
        default=default,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        required=required,
        namespace=namespace
    )


def config_get_volume_spec(submodule, provider_id, volume_name, is_secret=False, suffix=None):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    if is_secret:
        return {'name': volume_name, 'secret': {'secretName': resource_name}}
    else:
        return {'name': volume_name, 'configMap': {'name': resource_name}}


def config_interactive_set(submodule, provider_id=None, default_values=None, namespace=None,
                           is_secret=False, suffix=None, from_file=False, interactive=False):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    config_manager.interactive_set(
        default_values,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        namespace=namespace,
        from_file=from_file,
        interactive=interactive
    )


def get_resource_name(submodule, provider_id=None, suffix=None):
    return labels_manager.get_resource_name(get_resource_suffix(submodule, provider_id=provider_id, suffix=suffix))


def get_resource_suffix(submodule, provider_id=None, suffix=None):
    parts = ['provider', submodule]
    if provider_id:
        parts.append(provider_id)
    if suffix:
        parts.append(suffix)
    return '-'.join(parts)


def get_resource_labels(submodule, provider_id, extra_label_suffixes=None, for_deployment=False):
    label_suffixes = {
        'provider-submodule': submodule,
        'provider-id': provider_id,
    }
    if extra_label_suffixes:
        label_suffixes.update(**extra_label_suffixes)
    extra_labels = {'app': get_deployment_app_label(submodule, provider_id)} if for_deployment else {}
    return labels_manager.get_resource_labels(label_suffixes, extra_labels=extra_labels)


def get_deployment_app_label(submodule, provider_id):
    return get_resource_suffix(submodule, provider_id=provider_id)


def get_resource_annotations(submodule, provider_id=None, suffix=None):
    return annotations_manager.get_global_annotations()


def _get_submodule_ids_provider_or_provider_ids(submodule=None, provider_id=None):
    from ckan_cloud_operator.providers.db.proxy.constants import PROVIDER_SUBMODULE as db_proxy_provider_submodule
    from ckan_cloud_operator.providers.db.constants import PROVIDER_SUBMODULE as db_provider_submodule
    from ckan_cloud_operator.providers.db.web_ui.constants import PROVIDER_SUBMODULE as db_web_ui_submodule
    from ckan_cloud_operator.providers.users.constants import PROVIDER_SUBMODULE as users_provider_submodule
    from ckan_cloud_operator.providers.cluster.constants import PROVIDER_SUBMODULE as cluster_provider_submodule
    from ckan_cloud_operator.providers.storage.constants import PROVIDER_SUBMODULE as storage_provider_submodule

    if not submodule:
        return [
            db_proxy_provider_submodule,
            db_provider_submodule,
            db_web_ui_submodule,
            users_provider_submodule,
            cluster_provider_submodule,
            storage_provider_submodule
        ]

    ## db-proxy

    elif submodule == db_proxy_provider_submodule:
        from ckan_cloud_operator.providers.db.proxy.pgbouncer.constants import PROVIDER_ID as pgbouncer_provider_id

        if not provider_id:
            return [pgbouncer_provider_id]

        ## pgbouncer

        elif provider_id == pgbouncer_provider_id:
            from ckan_cloud_operator.providers.db.proxy.pgbouncer import manager as pgbouncer_manager

            return pgbouncer_manager

    ## db

    elif submodule == db_provider_submodule:
        from ckan_cloud_operator.providers.db.gcloudsql.constants import PROVIDER_ID as gcloudsql_provider_id

        if not provider_id:
            return [gcloudsql_provider_id]

        ## gcloud

        elif provider_id == gcloudsql_provider_id:
            from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager

            return gcloudsql_manager

    ## db-web-ui

    elif submodule == db_web_ui_submodule:
        from ckan_cloud_operator.providers.db.web_ui.adminer.constants import PROVIDER_ID as adminer_provider_id

        if not provider_id:
            return [adminer_provider_id]

        ## adminer

        elif provider_id == adminer_provider_id:
            from ckan_cloud_operator.providers.db.web_ui.adminer import manager as adminer_manager

            return adminer_manager

    ## users

    elif submodule == users_provider_submodule:
        from ckan_cloud_operator.providers.users.gcloud.constants import PROVIDER_ID as users_gcloud_provider_id

        if not provider_id:
            return [users_gcloud_provider_id]

        ## gcloud

        elif provider_id == users_gcloud_provider_id:
            from ckan_cloud_operator.providers.users.gcloud import manager as users_gcloud_manager

            return users_gcloud_manager

    ## cluster

    elif submodule == cluster_provider_submodule:
        from ckan_cloud_operator.providers.cluster.gcloud.constants import PROVIDER_ID as cluster_gcloud_provider_id

        if not provider_id:
            return [cluster_gcloud_provider_id]

        ## gcloud

        elif provider_id == cluster_gcloud_provider_id:
            from ckan_cloud_operator.providers.cluster.gcloud import manager as clouster_gcloud_manager

            return clouster_gcloud_manager

    ## storage

    elif submodule == storage_provider_submodule:
        from ckan_cloud_operator.providers.storage.minio.constants import PROVIDER_ID as storage_minio_provider_id

        if not provider_id:
            return [storage_minio_provider_id]

        ## minio

        elif provider_id == storage_minio_provider_id:
            from ckan_cloud_operator.providers.storage.minio import manager as storage_minio_manager

            return storage_minio_manager

    if not provider_id:
        return []
    else:
        return None
