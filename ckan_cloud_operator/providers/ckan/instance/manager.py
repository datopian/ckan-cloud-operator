import yaml
import time
import datetime
import binascii
import os
import traceback
import subprocess
import sys

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.providers.storage.constants import CONFIG_NAME
from ckan_cloud_operator.providers.storage.manager import get_provider_id as get_storage_provider_id
from ckan_cloud_operator.routers import manager as routers_manager

from ..constants import INSTANCE_NAME_CRD_SINGULAR
from ..constants import INSTANCE_CRD_SINGULAR
from ..deployment import manager as deployment_manager


def create(instance_type, instance_id=None, instance_name=None, values=None, values_filename=None, exists_ok=False,
           dry_run=False, update_=False, wait_ready=False, skip_deployment=False, skip_route=False, force=False):
    if not instance_id:
        if instance_name:
            instance_id = '{}-{}'.format(instance_name, _generate_password(6))
        else:
            instance_id = _generate_password(12)
    if values_filename:
        assert values is None
        if values_filename != '-':
            with open(values_filename) as f:
                values = yaml.load(f.read())
        else:
            values = yaml.load(sys.stdin.read())
    instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False)
    if not exists_ok and instance:
        raise Exception('instance already exists')
    values_id = values.get('id')
    if values_id and values_id != instance_id:
        logs.warning(f'changing instance id in spec from {values_id} to the instance id {instance_id}')
    values['id'] = instance_id

    use_cloud_storage = values.get('useCloudStorage') and config_manager.get('use-cloud-native-storage', secret_name=CONFIG_NAME)
    values['useCloudStorage'] = use_cloud_storage

    if instance:
        logs.info('Updating instance', instance_id=instance_id)
        instance['spec'] = values
        kubectl.apply(instance, dry_run=dry_run)
    else:
        logs.info('Creating instance', instance_id=instance_id)
        kubectl.apply(crds_manager.get_resource(
            INSTANCE_CRD_SINGULAR, instance_id,
            extra_label_suffixes={'instance-type': instance_type},
            spec=values
        ), dry_run=dry_run)

    if instance_name:
        set_name(instance_id, instance_name, dry_run=dry_run)

    if use_cloud_storage:
        set_storage(instance_id, instance_name, dry_run=dry_run)

    if update_:
        update(instance_id, wait_ready=wait_ready, skip_deployment=skip_deployment, skip_route=skip_route, force=force,
               dry_run=dry_run)

    return instance_id


def update(instance_id_or_name, override_spec=None, persist_overrides=False, wait_ready=False, skip_deployment=False,
           skip_route=False, force=False, dry_run=False):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name, required=not dry_run)
    if dry_run:
        logs.info('update instance', instance_id=instance_id, instance_id_or_name=instance_id_or_name,
                  override_spec=override_spec, persist_overrides=persist_overrides, wait_ready=wait_ready,
                  skip_deployment=skip_deployment, skip_route=skip_route, force=force, dry_run=dry_run)
    else:
        pre_update_hook_data = deployment_manager.pre_update_hook(instance_id, instance_type, instance, override_spec,
                                                                  skip_route)

        bucket_credentials = instance['spec'].get('ckanStorageBucket', {}).get(get_storage_provider_id())
        use_cloud_storage = bucket_credentials and config_manager.get('use-cloud-native-storage', secret_name=CONFIG_NAME)

        if use_cloud_storage:
            cluster_provider_id = cluster_manager.get_provider_id()

            if bucket_credentials:
                literal = []
                config_manager.set(
                    values=bucket_credentials,
                    secret_name='bucket-credentials',
                    namespace=instance_id
                )

        if persist_overrides:
            logs.info('Persisting overrides')
            kubectl.apply(instance)
        if not skip_deployment:
            deployment_manager.update(instance_id, instance_type, instance, force=force)
            if wait_ready:
                wait_instance_ready(instance_id_or_name)
        if not skip_route and pre_update_hook_data.get('sub-domain'):
            root_domain = pre_update_hook_data.get('root-domain')
            sub_domain = pre_update_hook_data['sub-domain']
            assert root_domain == routers_manager.get_default_root_domain(), 'invalid domain, must use default root domain'
            logs.info(f'adding instance default route to {sub_domain}.{root_domain}')
            routers_manager.create_subdomain_route('instances-default', {
                'target-type': 'ckan-instance',
                'ckan-instance-id': instance_id,
                'root-domain': root_domain,
                'sub-domain': sub_domain
            })
            logs.info(f'updating routers_manager wait_ready: {wait_ready}')
            routers_manager.update('instances-default', wait_ready)
        else:
            logs.info('skipping route creation', skip_route=skip_route, sub_domain=pre_update_hook_data.get('sub-domain'))
        logs.info('creating ckan admin')
        # Need to set in values.yaml
        if pre_update_hook_data.get('create-sysadmin'):
            ckan_admin_email = pre_update_hook_data.get('ckan-admin-email')
            ckan_admin_password = pre_update_hook_data.get('ckan-admin-password')
            ckan_admin_name = pre_update_hook_data.get('ckan-admin-name', 'admin')
            res = create_ckan_admin_user(instance_id, ckan_admin_name, ckan_admin_email, ckan_admin_password)
            logs.info(**res)
        logs.info('Instance is ready', instance_id=instance_id, instance_name=(instance_id_or_name if instance_id_or_name != instance_id else None))


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


def get_all_instances():
    return crds_manager.get(INSTANCE_CRD_SINGULAR)['items']


def list_instances(full=False, quick=False, withCredentials=False, name=None):
    if quick:
        for instance in get_all_instance_id_names():
            if name is not None and instance['name'] != name: continue
            yield {**instance, 'ready': None}
    else:
        for instance_data in get_all_instances():
            metadata_keys = ('name',)
            spec_keys = ('id', 'siteUrl', 'siteTitle', 'domain', 'registerSubdomain')
            try:
                spec = instance_data['spec']
                for k in spec_keys:
                    instance_data[k] = spec.get(k)
                metadata = instance_data['metadata']
                for k in metadata_keys:
                    instance_data[k] = metadata.get(k)
                instance_type = instance_data['metadata']['labels'].get('{}/instance-type'.format(labels_manager.get_label_prefix()))
                deployment = deployment_manager.get(instance_data['id'], instance_type, instance_data)
                instance_data['ready'] = deployment.get('ready')
            except Exception as e:
                pass
            if not full:
                instance_data = dict(
                    (k, v)
                    for k, v in instance_data.items()
                    if k in ('ready', *spec_keys, *metadata_keys)
                )
            if withCredentials:
                instance_data['admin_password'] = config_manager.get(
                    'CKAN_ADMIN_PASSWORD',
                    secret_name='ckan-admin-password',
                    namespace=instance_data['id']
                )
            yield instance_data


def delete_name(instance_name):
    crds_manager.delete(INSTANCE_NAME_CRD_SINGULAR, instance_name)


def set_name(instance_id, instance_name, dry_run=False):
    resource = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, name=instance_name, required=False)
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


def set_storage(instance_id, instance_name, dry_run=False):
    from ckan_cloud_operator.providers.storage.manager import get_provider, get_provider_id

    resource = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, name=instance_name, required=False)

    storage_provider = get_provider(default=None, provider_id=get_provider_id())
    bucket = storage_provider.create_bucket(instance_id, exists_ok=True, dry_run=dry_run)
    resource['spec']['ckanStorageBucket'] = {
        storage_provider.PROVIDER_ID: bucket
    }

    if dry_run:
        logs.print_yaml_dump(resource)
    else:
        kubectl.apply(resource)


def create_ckan_admin_user(instance_id_or_name, name, email=None, password=None, dry_run=False, use_paster=False):
    if not email:
        default_root_domain = routers_manager.get_default_root_domain()
        email = f'{name}@{instance_id_or_name}.{default_root_domain}'
    if not password:
        password = _generate_password(8)
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)
    user = {
        'name': name,
        'email': email,
        'password': password
    }
    if not dry_run:
        pod_name = _get_running_pod_name(instance_id)
        name, password, email = [user[k] for k in ['name', 'password', 'email']]
        logs.info(f'Creating CKAN admin user with {name} ({email}) on pod {pod_name}')

        if use_paster:
            logs.subprocess_check_call(
                f'echo y | kubectl -n {instance_id} exec -i {pod_name} -- ckan-paster --plugin=ckan sysadmin -c /etc/ckan/production.ini add {name} password={password} email={email}',
                shell=True
            )
        else:
            logs.subprocess_check_call(
                f'echo y | kubectl -n {instance_id} exec -i {pod_name} -- ckan --config /etc/ckan/production.ini sysadmin add {name} password={password} email={email}',
                shell=True
            )

    return {
        'instance-id': instance_id,
        'instance-type': instance_type,
        **{f'admin-{k}': v for k, v in user.items()},
        **({'dry-run': True} if dry_run else {}),
    }


def delete_ckan_admin_user(instance_id_or_name, name, dry_run=False, use_paster=False):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)

    if not dry_run:
        pod_name = _get_running_pod_name(instance_id)
        logs.info(f'Removing CKAN admin user {name} from sys-admins')

        if use_paster:
            logs.subprocess_check_call(
                f'echo y | kubectl -n {instance_id} exec -i {pod_name} -- ckan-paster --plugin=ckan sysadmin -c /etc/ckan/production.ini remove {name}',
                shell=True
            )
        else:
            logs.subprocess_check_call(
                f'echo y | kubectl -n {instance_id} exec -i {pod_name} -- ckan --config /etc/ckan/production.ini sysadmin remove {name}',
                shell=True
            )

def run_solr_commands(instance_id_or_name, command, dataset_id='', dry_run=False, use_paster=False):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)

    if not dry_run:
        pod_name = _get_running_pod_name(instance_id)
        logs.info(f'Running Search Index {command}')
        if use_paster:
            answer = logs.subprocess_check_output(
                f'kubectl -n {instance_id} exec -i {pod_name} -- ckan-paster --plugin=ckan -c /etc/ckan/production.ini search-index {command}',
                shell=True
            )
            for line in str(answer).replace('\\r', '\\n').split('\\n'):
                if line:
                    logs.info(str(line))
        else:
            answer = logs.subprocess_check_output(
                f'kubectl -n {instance_id} exec -i {pod_name} -- ckan --config /etc/ckan/production.ini search-index {command} {dataset_id}',
                shell=True
            )
            for line in str(answer).replace('\\r', '\\n').split('\\n'):
                if line:
                    logs.info(str(line))


def run_ckan_commands(instance_id_or_name, command, dry_run=False, use_paster=False):
    instance_id, instance_type, instance = _get_instance_id_and_type(instance_id_or_name)
    if not dry_run:
        pod_name = _get_running_pod_name(instance_id)
        logs.info(f'Running Search Index {command}')
        if use_paster:
            answer = logs.subprocess_check_output(
                f'kubectl -n {instance_id} exec -i {pod_name} -- ckan-paster --plugin=ckan -c /etc/ckan/production.ini {command}',
                shell=True
            )
            for line in str(answer).replace('\\r', '\\n').split('\\n'):
                if line:
                    logs.info(str(line))
        else:
            answer = logs.subprocess_check_output(
                f'kubectl -n {instance_id} exec -i {pod_name} -- ckan --config /etc/ckan/production.ini {command}',
                shell=True
            )
            for line in str(answer).replace('\\r', '\\n').split('\\n'):
                if line:
                    logs.info(str(line))


def _get_running_pod_name(instance_id):
    pod_name = None
    while not pod_name:
        try:
            pod_name = kubectl.get_deployment_pod_name('ckan', instance_id, use_first_pod=True, required_phase='Running')
            break
        except Exception as e:
            logs.warning('Failed to find running ckan pod', str(e))
        time.sleep(20)
    return pod_name



def _get_instance_id_and_type(instance_id_or_name=None, instance_id=None, required=True):
    if instance_id:
        logs.debug(f'Getting instance type using instance_id', instance_id=instance_id)
        instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False)
        instance_name = None
    else:
        logs.debug(f'Attempting to get instance type using id', instance_id_or_name=instance_id_or_name)
        instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id_or_name, required=False)
        if instance:
            instance_id = instance_id_or_name
            instance_name = None
        else:
            logs.debug(f'Attempting to get instance type from instance name', instance_id_or_name=instance_id_or_name)
            instance_name = crds_manager.get(INSTANCE_NAME_CRD_SINGULAR, name=instance_id_or_name, required=False)
            if instance_name:
                instance_id = instance_name['spec'].get('latest-instance-id')
                logs.debug(instance_id=instance_id)
                instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id, required=False)
                instance_name = instance_id_or_name
            else:
                instance_name = None
    if instance:
        instance_type = instance['metadata']['labels'].get('{}/instance-type'.format(labels_manager.get_label_prefix()))
    else:
        instance_type = None
    logs.debug_yaml_dump(instance_name=instance_name, instance_id=instance_id, instance_type=instance_type,
                         instance=bool(instance))
    if required:
        assert instance_id and instance_type and len(instance) > 2, f'Failed to find instance (instance_id_or_name={instance_id_or_name}, instance_id={instance_id})'
    return instance_id, instance_type, instance


def _generate_password(length):
    return binascii.hexlify(os.urandom(length)).decode()
