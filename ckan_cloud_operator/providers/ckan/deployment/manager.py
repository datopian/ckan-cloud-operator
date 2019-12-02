def initialize(interactive=False):
    from .helm.manager import initialize as ckan_helm_initialize
    ckan_helm_initialize(interactive=interactive)


def update(instance_id, instance_type, instance, force=False, dry_run=False):
    return _get_deployment_provider(instance_type).update(instance_id, instance, force=force, dry_run=dry_run)


def delete(instance_id, instance_type, instance):
    if not instance_type:
        # for case of delete instance after instance object was already delete
        # we assume it's a helm deployment to do cleanup of the namepsace
        instance_type = 'helm'
    return _get_deployment_provider(instance_type).delete(instance_id, instance)


def get(instance_id, instance_type, instance):
    return _get_deployment_provider(instance_type).get(instance_id, instance)


def get_backend_url(instance_id, instance_type, instance):
    deployment_provider = _get_deployment_provider(instance_type, required=False)
    if deployment_provider:
        return deployment_provider.get_backend_url(instance_id, instance)
    else:
        return None


def pre_update_hook(instance_id, instance_type, instance, override_spec, skip_route, dry_run=False):
    return _get_deployment_provider(instance_type).pre_update_hook(instance_id, instance, override_spec, skip_route,
                                                                   dry_run=dry_run)


def create_ckan_admin_user(instance_id, instance_type, instance, user):
    _get_deployment_provider(instance_type).create_ckan_admin_user(instance_id, instance, user)


def _get_deployment_provider(instance_type, required=True):
    if instance_type == 'helm':
        from .helm import manager as helm_manager
        return helm_manager
    elif required:
        raise Exception(f'unknown instance_type ({instance_type})')
    else:
        return None
