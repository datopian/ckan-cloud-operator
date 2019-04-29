def update(instance_id, instance_type, instance):
    return _get_deployment_provider(instance_type).update(instance_id, instance)


def get(instance_id, instance_type, instance):
    return _get_deployment_provider(instance_type).get(instance_id, instance)


def _get_deployment_provider(instance_type):
    if instance_type == 'helm':
        from .helm import manager as helm_manager
        return helm_manager
    else:
        raise Exception(f'unknown instance_type ({instance_type})')
