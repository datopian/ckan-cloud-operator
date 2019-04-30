import yaml
import time
import datetime
import binascii
import os
import traceback

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ..deployment import manager as deployment_manager

from ..constants import INSTANCE_NAME_CRD_SINGULAR
from ..constants import INSTANCE_CRD_SINGULAR


def create(instance_type, instance_id=None, instance_name=None, values=None, values_filename=None, exists_ok=False, dry_run=False):
    if not instance_id:
        if instance_name:
            instance_id = '{}-{}'.format(instance_name, _generate_password(6))
        else:
            instance_id = _generate_password(12)
    if values_filename:
        assert values is None
        with open(values_filename) as f:
            values = yaml.load(f.read())
    if not exists_ok and crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False):
        raise Exception('instance already exists')
    logs.info('Creating instance', instance_id=instance_id)
    kubectl.apply(crds_manager.get_resource(
        INSTANCE_CRD_SINGULAR, instance_id,
        extra_label_suffixes={'instance-type': instance_type},
        spec=values
    ), dry_run=dry_run)
    if instance_name:
        set_name(instance_id, instance_name, dry_run=dry_run)


def update(instance_id_or_name, override_spec=None, persist_overrides=False, wait_ready=False, skip_deployment=False):
    instance, instance_id, instance_type = _get_instance_id_and_type(instance_id_or_name)
    if override_spec:
        for k, v in override_spec.items():
            logs.info(f'Applying override spec {k}={v}')
            instance['spec'][k] = v
    if persist_overrides:
        logs.info('Persisting overrides')
        kubectl.apply(instance)
    if not skip_deployment:
        deployment_manager.update(instance_id, instance_type, instance)
    if wait_ready:
        wait_instance_ready(instance_id_or_name)


def delete(instance_id):
    try:
        instance, instance_id, instance_type = _get_instance_id_and_type(instance_id=instance_id)
    except Exception:
        logs.error(traceback.format_exc())
        instance, instance_type = None, None
    deployment_manager.delete(instance_id, instance_type, instance)
    crds_manager.delete(INSTANCE_CRD_SINGULAR, instance_id)


def wait_instance_ready(instance_id_or_name):
    logs.info(f'Waiting for instance ready status ({instance_id_or_name})')
    time.sleep(3)
    while True:
        data = get(instance_id_or_name)
        if data.get('ready'):
            break
        else:
            logs.print_yaml_dump(
                {
                    k: v for k, v in data.items()
                    if (k not in ['ready'] and type(v) == dict and not v.get('ready')) or k == 'namespace'
                }
            )
            time.sleep(2)


def get(instance_id_or_name, attr=None, exclude_attr=None):
    """Get detailed information about the instance and related components"""
    instance, instance_id, instance_type = _get_instance_id_and_type(instance_id_or_name)
    gets = {
        'deployment': lambda: deployment_manager.get(instance_id, instance_type, instance),
    }
    if exclude_attr:
        gets = {k: v for k, v in gets.items() if k not in exclude_attr}
    if attr:
        return gets[attr]()
    else:
        ret = {'ready': True}
        for k, v in gets.items():
            ret[k] = v()
            if type(ret[k]) == dict and not ret[k].get('ready'):
                ret['ready'] = False
        ret['id'] = instance_id
        return ret


def get_all_instance_id_names():
    instance_names = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, required=False)
    instance_name_ids = {}
    if instance_names:
        for instance_name in instance_names['items']:
            instance_name_ids[instance_name['spec']['latest-instance-id']] = instance_name['spec']['name']
    label_prefix = labels_manager.get_label_prefix()
    for instance in crds_manager.get(INSTANCE_CRD_SINGULAR)['items']:
        instance_id = instance['metadata']['labels'][f'{label_prefix}/crd-ckaninstance-name']
        instance_name = instance_name_ids.pop(instance_id, None)
        yield {'id': instance_id, 'name': instance_name}
    for instance_id, instance_name in instance_name_ids.items():
        yield {'id': instance_id, 'name': instance_name}


def list_instances(full=False, quick=False, name=None):
    for instance in get_all_instance_id_names():
        if name is not None and instance['name'] != name: continue
        if quick:
            yield {**instance, 'ready': None}
        else:
            try:
                instance_data = get(instance['id'])
            except Exception:
                instance_data = {}
            if full:
                instance_data['name'] = instance['name']
                yield instance_data
            else:
                yield {**instance, 'ready': instance_data.get('ready')}


def delete_name(instance_name):
    crds_manager.delete(INSTANCE_NAME_CRD_SINGULAR, instance_name)


def set_name(instance_id, instance_name, dry_run=False):
    resource = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, instance_name, required=False)
    if resource:
        resource['spec']['latest-instance-id'] = instance_id
        if not resource['spec']['instance-ids'].get(instance_id):
            resource['spec']['instance-ids'][instance_id] = {'added': datetime.datetime.now()}
    else:
        resource = crds_manager.get_resource(
            INSTANCE_NAME_CRD_SINGULAR, instance_name,
            spec={
                'name': instance_name,
                'latest-instance-id': instance_id,
                'instance-ids': {
                    instance_id: {'added': datetime.datetime.now()}
                }
            }
        )
    if dry_run:
        logs.print_yaml_dump(resource)
    else:
        kubectl.apply(resource)


def _get_instance_id_and_type(instance_id_or_name=None, instance_id=None):
    if instance_id:
        instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False)
    else:
        instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id_or_name, required=False)
        if instance:
            instance_id = instance_id_or_name
    if not instance:
        assert not instance_id
        instance_name = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, name=instance_id_or_name, required=False)
        if instance_name:
            instance_id = instance_name['spec'].get('latest-instance-id')
            instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False)
        else:
            instance_id = None
    instance_type = instance['metadata']['labels'].get('{}/instance-type'.format(labels_manager.get_label_prefix())) if instance else None
    return instance, instance_id, instance_type


def _generate_password(length):
    return binascii.hexlify(os.urandom(length)).decode()
