def update(instance_id, instance_type, instance):
    return _get_deployment_provider(instance_type).update(instance_id, instance)


def delete(instance_id, instance_type, instance):
    if not instance_type:
        # for case of delete instance after instance object was already delete
        # we assume it's a helm deployment to do cleanup of the namepsace
        instance_type = 'helm'
    return _get_deployment_provider(instance_type).delete(instance_id, instance)


def get(instance_id, instance_type, instance):
    return _get_deployment_provider(instance_type).get(instance_id, instance)


def _get_deployment_provider(instance_type):
    if instance_type == 'helm':
        from .helm import manager as helm_manager
        return helm_manager
    else:
        raise Exception(f'unknown instance_type ({instance_type})')
