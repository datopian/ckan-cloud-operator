import datetime

from ckan_cloud_operator import kubectl

from ckan_cloud_operator.labels import manager as labels_manager


def get_global_annotations(with_timestamp=True):
    label_prefix = labels_manager.get_label_prefix()
    return {
        f'{label_prefix}/operator-timestamp': str(datetime.datetime.now())
    } if with_timestamp else {}


def set_status(resource, prefix, status):
    _annotate(resource, f'{prefix}-{status}=true')


def get_status(resource, prefix, status=None):
    if status:
        return bool(_get_annotation(resource, f'{prefix}-{status}'))
    else:
        label_prefix = labels_manager.get_label_prefix()
        prefix = f'{label_prefix}/{prefix}'
        statuses = set()
        for k, v in resource['metadata'].get('annotations', {}).items():
            if k.startswith(prefix):
                statuses.add(k.replace(prefix, ''))
        return list(statuses)


def _annotate(resource, *annotations, overwrite=True):
    label_prefix = labels_manager.get_label_prefix()
    kind = resource['kind']
    namespace = resource['metadata']['namespace']
    name = resource['metadata']['name']
    cmd = f'annotate {kind} {name}'
    for annotation in annotations:
        cmd += f' {label_prefix}/{annotation}'
    if overwrite:
        cmd += ' --overwrite'
    kubectl.check_call(cmd, namespace)


def _get_annotation(resource, annotation, default=None):
    label_prefix = labels_manager.get_label_prefix()
    return resource['metadata'].get('annotations', {}).get(f'{label_prefix}/{annotation}', default)
