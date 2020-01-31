from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.annotations import manager as annotations_manager


def get_provider(submodule, required=True, supported_provider_ids=None, default=None, verbose=False, provider_id=None):
    if default: required = False
    if not provider_id:
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


def config_get(submodule, provider_id=None, key=None, default=None, required=False, namespace=None, is_secret=False,
               suffix=None, template=None):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    return config_manager.get(
        key=key,
        default=default,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        required=required,
        namespace=namespace,
        template=template
    )


def config_get_volume_spec(submodule, provider_id, volume_name, is_secret=False, suffix=None):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    if is_secret:
        return {'name': volume_name, 'secret': {'secretName': resource_name}}
    else:
        return {'name': volume_name, 'configMap': {'name': resource_name}}


def config_interactive_set(submodule, provider_id=None, default_values=None, namespace=None,
                           is_secret=False, suffix=None, from_file=False, interactive=True):
    resource_name = get_resource_name(submodule, provider_id=provider_id, suffix=suffix)
    config_manager.interactive_set(
        default_values,
        secret_name=resource_name if is_secret else None,
        configmap_name=None if is_secret else resource_name,
        namespace=namespace,
        from_file=from_file,
        interactive=interactive
    )


def get_resource_name(submodule, provider_id=None, suffix=None, short=False):
    return labels_manager.get_resource_name(get_resource_suffix(submodule, provider_id=provider_id, suffix=suffix,
                                                                short=short), short=short)


def get_resource_suffix(submodule, provider_id=None, suffix=None, short=False):
    if short:
        res = _get_submodule_provider_config(submodule, provider_id).get('short-resource-suffix')
        assert res, f'Failed to get short-resource-suffix ({submodule}={provider_id})'
        if suffix:
            res += suffix
        return res
    else:
        parts = ['provider', submodule]
        if provider_id:
            parts.append(provider_id)
        if suffix:
            parts.append(suffix)
        return '-'.join(parts)


def get_resource_labels(submodule, provider_id, extra_label_suffixes=None, for_deployment=False, suffix=None):
    label_suffixes = {
        'provider-submodule': submodule,
        'provider-id': provider_id,
    }
    if suffix:
        label_suffixes['provider-submodule-suffix'] = suffix
    if extra_label_suffixes:
        label_suffixes.update(**extra_label_suffixes)
    extra_labels = {'app': get_deployment_app_label(submodule, provider_id, suffix=suffix)} if for_deployment else {}
    return labels_manager.get_resource_labels(label_suffixes, extra_labels=extra_labels)


def get_deployment_app_label(submodule, provider_id, suffix=None):
    return get_resource_suffix(submodule, provider_id=provider_id, suffix=suffix)


def get_resource_annotations(submodule, provider_id=None, suffix=None, with_timestamp=True):
    return annotations_manager.get_global_annotations(with_timestamp=with_timestamp)


def _get_submodule_provider_config(submodule, provider_id):
    return {
        'apps-deployment': {
            'helm': {
                'short-resource-suffix': 'app-helm'
            }
        }
    }.get(submodule, {}).get(provider_id, {})


def _get_submodule_ids_provider_or_provider_ids(submodule=None, provider_id=None):
    from ckan_cloud_operator.providers.db.proxy.constants import PROVIDER_SUBMODULE as db_proxy_provider_submodule
    from ckan_cloud_operator.providers.db.constants import PROVIDER_SUBMODULE as db_provider_submodule
    from ckan_cloud_operator.providers.db.web_ui.constants import PROVIDER_SUBMODULE as db_web_ui_submodule
    from ckan_cloud_operator.providers.users.constants import PROVIDER_SUBMODULE as users_provider_submodule
    from ckan_cloud_operator.providers.cluster.constants import PROVIDER_SUBMODULE as cluster_provider_submodule
    from ckan_cloud_operator.providers.storage.constants import PROVIDER_SUBMODULE as storage_provider_submodule
    from ckan_cloud_operator.providers.solr.constants import PROVIDER_SUBMODULE as solr_provider_submodule

    if not submodule:
        return [
            db_proxy_provider_submodule,
            db_provider_submodule,
            db_web_ui_submodule,
            users_provider_submodule,
            cluster_provider_submodule,
            storage_provider_submodule,
            solr_provider_submodule
        ]

    ## db-proxy

    elif submodule == db_proxy_provider_submodule:
        from ckan_cloud_operator.providers.db.proxy.pgbouncer.constants import PROVIDER_ID as pgbouncer_provider_id
        from ckan_cloud_operator.providers.db.proxy.gcloudsql.constants import PROVIDER_ID as db_proxy_gcloudsql_provider_id
        from ckan_cloud_operator.providers.db.proxy.rds.constants import PROVIDER_ID as db_proxy_rds_provider_id

        if not provider_id:
            return [pgbouncer_provider_id, db_proxy_gcloudsql_provider_id, db_proxy_rds_provider_id]

        ## pgbouncer

        elif provider_id == pgbouncer_provider_id:
            from ckan_cloud_operator.providers.db.proxy.pgbouncer import manager as pgbouncer_manager

            return pgbouncer_manager

        ## gcloudsql proxy

        elif provider_id == db_proxy_gcloudsql_provider_id:
            from ckan_cloud_operator.providers.db.proxy.gcloudsql import manager as db_proxy_gcloudsql_manager

            return db_proxy_gcloudsql_manager

        ## rds proxy

        elif provider_id == db_proxy_rds_provider_id:
            from ckan_cloud_operator.providers.db.proxy.rds import manager as db_proxy_rds_manager

            return db_proxy_rds_manager

    ## db

    elif submodule == db_provider_submodule:
        from ckan_cloud_operator.providers.db.azuresql.constants import PROVIDER_ID as azuresql_provider_id
        from ckan_cloud_operator.providers.db.gcloudsql.constants import PROVIDER_ID as gcloudsql_provider_id
        from ckan_cloud_operator.providers.db.rds.constants import PROVIDER_ID as rds_provider_id
        from ckan_cloud_operator.providers.db.minikube.constants import PROVIDER_ID as minikube_provider_id

        if not provider_id:
            return [gcloudsql_provider_id]

        ## gcloud

        elif provider_id == gcloudsql_provider_id:
            from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager

            return gcloudsql_manager

        ## rds

        elif provider_id == rds_provider_id:
            from ckan_cloud_operator.providers.db.rds import manager as rds_manager

            return rds_manager

        ## azuresql

        elif provider_id == azuresql_provider_id:
            from ckan_cloud_operator.providers.db.azuresql import manager as azuresql_manager

            return azuresql_manager

        ## minikube

        elif provider_id == minikube_provider_id:
            from ckan_cloud_operator.providers.db.minikube import manager as minikube_manager

            return minikube_manager

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
        from ckan_cloud_operator.providers.users.rancher.constants import PROVIDER_ID as users_rancher_provider_id

        if not provider_id:
            return [users_gcloud_provider_id, users_rancher_provider_id]

        ## gcloud

        elif provider_id == users_gcloud_provider_id:
            from ckan_cloud_operator.providers.users.gcloud import manager as users_gcloud_manager

            return users_gcloud_manager

        ## rancher

        elif provider_id == users_rancher_provider_id:
            from ckan_cloud_operator.providers.users.rancher import manager as users_rancher_manager

            return users_rancher_manager

    ## cluster

    elif submodule == cluster_provider_submodule:
        from ckan_cloud_operator.providers.cluster.gcloud.constants import PROVIDER_ID as cluster_gcloud_provider_id
        from ckan_cloud_operator.providers.cluster.aws.constants import PROVIDER_ID as cluster_aws_provider_id
        from ckan_cloud_operator.providers.cluster.azure.constants import PROVIDER_ID as cluster_azure_provider_id
        from ckan_cloud_operator.providers.cluster.minikube.constants import PROVIDER_ID as cluster_minikube_provider_id

        if not provider_id:
            return [cluster_gcloud_provider_id, cluster_aws_provider_id, cluster_azure_provider_id]

        ## gcloud

        elif provider_id == cluster_gcloud_provider_id:
            from ckan_cloud_operator.providers.cluster.gcloud import manager as clouster_gcloud_manager

            return clouster_gcloud_manager

        ## aws

        elif provider_id == cluster_aws_provider_id:
            from ckan_cloud_operator.providers.cluster.aws import manager as cluster_aws_manager

            return cluster_aws_manager

        ## azure

        elif provider_id == cluster_azure_provider_id:
            from ckan_cloud_operator.providers.cluster.azure import manager as cluster_azure_manager

            return cluster_azure_manager

        ## minikube

        elif provider_id == cluster_minikube_provider_id:
            from ckan_cloud_operator.providers.cluster.minikube import manager as cluster_minikube_manager

            return cluster_minikube_manager

    ## storage

    elif submodule == storage_provider_submodule:
        from ckan_cloud_operator.providers.storage.azure.constants import PROVIDER_ID as storage_azure_provider_id
        from ckan_cloud_operator.providers.storage.gcloud.constants import PROVIDER_ID as storage_gcloud_provider_id
        from ckan_cloud_operator.providers.storage.minio.constants import PROVIDER_ID as storage_minio_provider_id
        from ckan_cloud_operator.providers.storage.s3.constants import PROVIDER_ID as storage_s3_provider_id

        if not provider_id:
            return []

        # Azure
        elif provider_id == storage_azure_provider_id:
            from ckan_cloud_operator.providers.storage.azure import manager as storage_azure_manager

            return storage_azure_manager

        # Gcloud
        elif provider_id == storage_gcloud_provider_id:
            from ckan_cloud_operator.providers.storage.gcloud import manager as storage_gcloud_manager

            return storage_gcloud_manager

        # Minio
        elif provider_id == storage_minio_provider_id:
            from ckan_cloud_operator.providers.storage.minio import manager as storage_minio_manager

            return storage_minio_manager

        # AWS
        elif provider_id == storage_s3_provider_id:
            from ckan_cloud_operator.providers.storage.s3 import manager as storage_s3_manager

            return storage_s3_manager


    ## solr

    elif submodule == solr_provider_submodule:
        from ckan_cloud_operator.providers.solr.solrcloud.constants import PROVIDER_ID as solr_solrcloud_provider_id

        if not provider_id:
            return [solr_solrcloud_provider_id]

        ## solrcloud

        elif provider_id == solr_solrcloud_provider_id:
            from ckan_cloud_operator.providers.solr.solrcloud import manager as solr_solrcloud_manager

            return solr_solrcloud_manager

    if not provider_id:
        return []
    else:
        return None
