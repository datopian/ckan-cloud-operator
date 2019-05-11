from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

from ckan_cloud_operator.config import manager as config_manager


def initialize(log_kwargs=None):
    logs.info('setting label-prefix: ckan-cloud', **(log_kwargs or {}))
    config_manager.set('label-prefix', 'ckan-cloud')


def get_label_prefix(short=False):
    """Returns a global label prefix which should be used to namespace operator objects"""
    return config_manager.get('short-label-prefix' if short else 'label-prefix', required=True)


def get_resource_name(suffix, short=False):
    label_prefix = get_label_prefix(short=short)
    if short:
        return f'{label_prefix}{suffix}'
    else:
        return f'{label_prefix}-{suffix}'


def get_resource_labels(label_suffixes, extra_labels=None):
    label_prefix = get_label_prefix()
    labels = {
        f'{label_prefix}/{label_suffix}': label_value
        for label_suffix, label_value in label_suffixes.items()
    }
    if extra_labels:
        labels.update(**extra_labels)
    return labels


def delete_by_labels(labels, kinds):
    kubectl.delete_items_by_labels(kinds, labels)
