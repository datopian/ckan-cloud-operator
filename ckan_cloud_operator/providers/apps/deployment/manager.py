from ckan_cloud_operator.labels import manager as labels_manager


def update(instance_id, instance, dry_run=False):
    return _get_deployment_provider(instance).update(instance_id, instance, dry_run=dry_run)


def delete(instance_id, instance):
    return _get_deployment_provider(instance).delete(instance_id, instance)


def get(instance_id, instance):
    return _get_deployment_provider(instance).get(instance_id, instance)


def get_backend_url(instance_id, instance):
    deployment_provider = _get_deployment_provider(instance, required=False)
    if deployment_provider:
        return deployment_provider.get_backend_url(instance_id, instance)
    else:
        return None


def pre_update_hook(instance_id, instance, override_spec, skip_route, dry_run=False):
    return _get_deployment_provider(instance).pre_update_hook(instance_id, instance, override_spec, skip_route,
                                                              dry_run=dry_run)


def create_ckan_admin_user(instance_id, instance, user):
    _get_deployment_provider(instance).create_ckan_admin_user(instance_id, instance, user)


def _get_deployment_provider(instance, required=True):
    for get_provider in [_get_helm_deployment_provider]:
        res = get_provider(instance)
        if res:
            break
    if not res and required:
        raise Exception(f'failed to find provider for instance')
    else:
        return res


def _get_helm_deployment_provider(instance):
    label_prefix = labels_manager.get_label_prefix()
    if instance['metadata'].get('annotations', {}).get(f'{label_prefix}/deployment-provider') == 'helm':
        from .helm import manager as helm_manager
        return helm_manager
    else:
        return None
