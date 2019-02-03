from ckan_cloud_operator.config.manager import get_label_prefix


def get_provider_labels(submodule, provider_id, for_deployment=False):
    label_prefix = get_label_prefix()
    labels = {
        f'{label_prefix}/provider-submodule': submodule,
        f'{label_prefix}/provider-id': provider_id,
    }
    if for_deployment:
        labels['app'] = f'{label_prefix}-{submodule}-{provider_id}'
    return labels


def get_provider_label_prefix(submodule, provider_id):
    label_prefix = get_label_prefix()
    return f'{label_prefix}-{submodule}-{provider_id}'
