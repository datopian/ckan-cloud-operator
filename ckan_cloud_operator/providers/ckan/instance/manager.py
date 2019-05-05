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
from ckan_cloud_operator.routers import manager as routers_manager

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
    values_id = values.get('id')
    if values_id:
        assert values_id == instance_id, f'instance spec has conflicting instance_id ({values_id} != {instance_id})'
    values['id'] = instance_id
    logs.info('Creating instance', instance_id=instance_id)
    kubectl.apply(crds_manager.get_resource(
        INSTANCE_CRD_SINGULAR, instance_id,
        extra_label_suffixes={'instance-type': instance_type},
        spec=values
    ), dry_run=dry_run)
    if instance_name:
        set_name(instance_id, instance_name, dry_run=dry_run)
    return instance_id


def update(instance_id_or_name, override_spec=None, persist_overrides=False, wait_ready=False, skip_deployment=False, skip_route=False):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)
    if override_spec:
        for k, v in override_spec.items():
            logs.info(f'Applying override spec {k}={v}')
            instance['spec'][k] = v
    assert instance['spec'].get('useCentralizedInfra'), 'non-centralized instances are not supported'
    # full domain to route to the instance
    instance_domain = instance['spec'].get('domain')
    # instance is added to router only if this is true, as all routers must use SSL and may use sans SSL too
    with_sans_ssl = instance['spec'].get('withSansSSL')
    # subdomain to register on the default root domain
    register_subdomain = instance['spec'].get('registerSubdomain')
    if persist_overrides:
        logs.info('Persisting overrides')
        kubectl.apply(instance)
    if not skip_deployment:
        deployment_manager.update(instance_id, instance_type, instance)
        if wait_ready:
            wait_instance_ready(instance_id_or_name)
    if not skip_route:
        if instance_domain:
            assert with_sans_ssl, 'withSansSSL must be set to true to add routes'
            assert '.'.join(instance_domain.split('.')[1:]) == routers_manager.get_default_root_domain(), f'invalid root domain ({instance_domain})'
            assert instance_domain.split('.')[0] == register_subdomain, f'invalid register_subdomain ({register_subdomain})'
            logs.info(f'adding instance route to {instance_domain}')
            routers_manager.create_subdomain_route('instances-default', {
                'target-type': 'ckan-instance',
                'ckan-instance-id': instance_id,
                'root-domain': routers_manager.get_default_root_domain(),
                'sub-domain': register_subdomain
            })
            routers_manager.update('instances-default', wait_ready)
        else:
            assert not register_subdomain, 'subdomain registration is only supported with instance_domain'


def delete(instance_id):
    try:
        instance_id, instance_type, instance = _get_instance_id_and_type(instance_id=instance_id)
    except Exception:
        logs.error(traceback.format_exc())
        instance, instance_type = None, None
    try:
        deployment_manager.delete(instance_id, instance_type, instance)
    except Exception as e:
        logs.error('error during deployment delete', error=str(e))
    try:
        crds_manager.delete(INSTANCE_CRD_SINGULAR, instance_id)
    except Exception as e:
        logs.error('error during crd delete', error=str(e))


def delete_instances(instance_ids_or_names=None, dry_run=True, instance_ids=None):
    if instance_ids:
        assert not instance_ids_or_names
        use_instance_ids = True
    else:
        assert not instance_ids
        use_instance_ids = False
    logs.info(use_instance_ids=use_instance_ids, instance_ids=instance_ids, instance_ids_or_names=instance_ids_or_names)
    for instance_id_or_name in (instance_ids if use_instance_ids else instance_ids_or_names):
        logs.info(instance_id_or_name=instance_id_or_name)
        if use_instance_ids:
            instance_id = instance_id_or_name
        else:
            instance_id, _, _ = _get_instance_id_and_type(instance_id_or_name)
        instance_name = instance_id_or_name if instance_id != instance_id_or_name else None
        yield {
            'id': instance_id,
            **({'name': instance_name} if instance_name else {})
        }
        errors = []
        if instance_id:
            if not dry_run:
                try:
                    delete(instance_id=instance_id)
                except Exception as e:
                    errors.append(str(e))
                    logs.error('exception raised during instance deletion, '
                               'this does not always indicate deletion was not successful',
                               exception=str(e))
        else:
            errors.append(f'Failed to get instance_id for instance_id_or_name {instance_id_or_name}')
        if instance_name:
            try:
                delete_name(instance_name)
            except Exception as e:
                errors.append(str(e))
                logs.error('exception raised during instance name deletion.', exception=str(e))
        yield {'errors': errors}


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


def edit(instance_id_or_name):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)
    crds_manager.edit(INSTANCE_CRD_SINGULAR, name=instance_id)


def get(instance_id_or_name, attr=None, exclude_attr=None, with_spec=False):
    """Get detailed information about the instance and related components"""
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)
    if not exclude_attr:
        exclude_attr = []
    if not with_spec:
        exclude_attr.append('spec')
    gets = {
        'deployment': lambda: deployment_manager.get(instance_id, instance_type, instance),
        'spec': lambda: instance['spec']
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


def get_backend_url(instance_id_or_name=None, instance_id=None):
    return deployment_manager.get_backend_url(*_get_instance_id_and_type(instance_id_or_name, instance_id=instance_id))


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
    return instance_id, instance_type, instance


def _generate_password(length):
    return binascii.hexlify(os.urandom(length)).decode()
