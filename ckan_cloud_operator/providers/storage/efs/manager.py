#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False, suffix=None): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment, suffix=suffix)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False, interactive=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file, interactive)

################################
# custom provider code starts here
#

import os
import binascii
import yaml
import json

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.cluster.aws import manager as aws_manager


def initialize(interactive=False, dry_run=False):
    aws_creds = aws_manager.get_aws_credentials()
    _config_interactive_set({
        'file.system.id': None,
    }, interactive=interactive, namespace='default')
    for key, value in [
        ('aws.region', aws_creds['region']),
        ('provisioner.name', 'example.com/aws-efs'),
        # ('dns.name', ''),
    ]:
        _config_set(key=key, value=value, namespace='default')
    _apply_rbac()
    _apply_deployment()


def _apply_rbac():
    labels = _get_resource_labels()
    rbac.update_service_account('efs-provisioner', labels, 'default')
    rbac.update_cluster_role('efs-provisioner-runner', [
        dict(zip(['apiGroups', 'resources', 'verbs'], rule))
        for rule in (
            ([''], ['persistentvolumes'], ['get', 'list', 'watch', 'create', 'delete']),
            ([''], ['persistentvolumeclaims'], ['get', 'list', 'watch', 'update']),
            (['storage.k8s.io'], ['storageclasses'], ['get', 'list', 'watch']),
            ([''], ['events'], ['create', 'update', 'patch']),
        )
    ], labels)
    rbac.update_cluster_role_binding('run-efs-provisioner',  dict(
            kind='ServiceAccount', name='efs-provisioner', namespace='default',
    ), 'efs-provisioner-runner', labels)
    rbac.update_role('leader-locking-efs-provisioner', labels, [dict(
            apiGroups=[''],
            resources=['endpoints'],
            verbs=['get', 'list', 'watch', 'create', 'update', 'patch']
    )], 'default')
    rbac.update_role_binding('leader-locking-efs-provisioner', 'leader-locking-efs-provisioner', 'default', 'efs-provisioner', labels)

def _apply_deployment():
    labels = _get_resource_labels(for_deployment=True)
    labels = dict(labels, app='efs-provisioner')
    configmap_name = _get_resource_name()
    fs_id = _config_get('file.system.id', namespace='default')
    aws_region = _config_get('aws.region', namespace='default')
    kubectl.apply(kubectl.get_deployment(
        'efs-provisioner',
        labels,
        dict(
            replicas=1,
            strategy=dict(type='Recreate'),
            selector=dict(matchLabels=labels),
            template=dict(
                metadata=dict(labels=labels),
                spec=dict(
                    containers=[dict(
                        name='efs-provisioner',
                        image='quay.io/external_storage/efs-provisioner:latest',
                        env=[
                            dict(
                                name=name,
                                valueFrom=dict(
                                    configMapKeyRef=dict(
                                        name=configmap_name,
                                        key=key,
                                        optional=optional
                                    )
                                )
                            )
                            for name, key, optional in [
                                ('FILE_SYSTEM_ID', 'file.system.id', False),
                                ('AWS_REGION', 'aws.region', False),
                                ('DNS_NAME', 'dns.name', True),
                                ('PROVISIONER_NAME', 'provisioner.name', False),
                            ]
                        ],
                        volumeMounts=[dict(
                            name='pv-volume',
                            mountPath='/persistentvolumes'
                        )]
                    )],
                    volumes=[dict(
                        name='pv-volume',
                        nfs=dict(
                            server=f'{fs_id}.efs.{aws_region}.amazonaws.com',
                            path='/'
                        )
                    )]
                )
            )
        ),
        namespace='default'
    ))

#         dry_run=dry_run
#     )
#     _apply_service(storage_suffix=storage_suffix, dry_run=dry_run)
#     if not storage_suffix:
#         _update_route(storage_suffix=storage_suffix, dry_run=dry_run)
#         _set_provider()


# def print_credentials(raw=False, storage_suffix=None):
#     hostname, access_key, secret_key = get_credentials(storage_suffix=storage_suffix)
#     if raw:
#         print(f'https://{hostname} {access_key} {secret_key}')
#     else:
#         print('Minio admin credentials:')
#         print('External Domain: ' + hostname)
#         print('Access Key: ' + access_key)
#         print('Secret Key: ' + secret_key)
#         print('\nto use with minio-client, run the following command:')
#         print(f'mc config host add my-storage https://{hostname} {access_key} {secret_key}')



# def get_credentials(storage_suffix=None):
#     return [_get_frontend_hostname(storage_suffix=storage_suffix)] + [
#         _config_get(key, required=True, is_secret=True, suffix=storage_suffix)
#         for key in ['MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY']
#     ]


# def _generate_password(l):
#     return binascii.hexlify(os.urandom(l)).decode()


# def _apply_secret(storage_suffix=None):
#     access_key = _config_get('MINIO_ACCESS_KEY', required=False, is_secret=True, suffix=storage_suffix) or _generate_password(8)
#     secret_key = _config_get('MINIO_SECRET_KEY', required=False, is_secret=True, suffix=storage_suffix) or _generate_password(12)
#     _config_set(values={'MINIO_ACCESS_KEY': access_key, 'MINIO_SECRET_KEY': secret_key}, is_secret=True, suffix=storage_suffix)


# def _apply_deployment(volume_spec, storage_suffix=None, dry_run=False):
#     node_selector = volume_spec.pop('nodeSelector', None)
#     if node_selector:
#         pod_scheduling = {'nodeSelector': node_selector}
#     else:
#         pod_scheduling = {}
#     container_spec_overrides = _config_get('container-spec-overrides', required=False, default=None, suffix=storage_suffix)
#     kubectl.apply(kubectl.get_deployment(
#         _get_resource_name(suffix=storage_suffix),
#         _get_resource_labels(for_deployment=True, suffix=storage_suffix),
#         {
#             'replicas': 1,
#             'revisionHistoryLimit': 10,
#             'strategy': {'type': 'Recreate', },
#             'template': {
#                 'metadata': {
#                     'labels': _get_resource_labels(for_deployment=True, suffix=storage_suffix),
#                     'annotations': _get_resource_annotations(suffix=storage_suffix)
#                 },
#                 'spec': {
#                     **pod_scheduling,
#                     'containers': [
#                         {
#                             'name': 'minio',
#                             'image': 'minio/minio',
#                             'args': ['server', '/export'],
#                             'envFrom': [{'secretRef': {'name': _get_resource_name(suffix=storage_suffix)}}],
#                             'ports': [{'containerPort': 9000}],
#                             'volumeMounts': [
#                                 {
#                                     'name': 'minio-data',
#                                     'mountPath': '/export',
#                                 }
#                             ],
#                             **(json.loads(container_spec_overrides) if container_spec_overrides else {})
#                         }
#                     ],
#                     'volumes': [
#                         dict(volume_spec, name='minio-data')
#                     ]
#                 }
#             }
#         }
#     ), dry_run=dry_run)


# def _apply_service(storage_suffix=None, dry_run=False):
#     kubectl.apply(kubectl.get_resource(
#         'v1', 'Service',
#         _get_resource_name(suffix=storage_suffix),
#         _get_resource_labels(suffix=storage_suffix),
#         spec={
#             'ports': [
#                 {'name': '9000', 'port': 9000}
#             ],
#             'selector': {
#                 'app': _get_resource_labels(for_deployment=True, suffix=storage_suffix)['app']
#             }
#         }
#     ), dry_run=dry_run)


# def _get_or_create_volume(storage_suffix=None, use_existing_disk_name=None, zone=0):
#     disk_size_gb = _config_get('disk-size-gb', required=True, suffix=storage_suffix)
#     volume_spec = _config_get('volume-spec', required=False, suffix=storage_suffix)
#     if volume_spec:
#         volume_spec = yaml.load(volume_spec)
#     else:
#         from ckan_cloud_operator.providers.cluster import manager as cluster_manager
#         volume_spec = cluster_manager.create_volume(
#             disk_size_gb,
#             _get_resource_labels(suffix=storage_suffix),
#             use_existing_disk_name=use_existing_disk_name, zone=zone
#         )
#         _config_set('volume-spec', yaml.dump(volume_spec, default_flow_style=False), suffix=storage_suffix)
#     return volume_spec


# def _update_route(storage_suffix=None, dry_run=False):
#     backend_url_target_id = _get_backend_url_target_id(storage_suffix=storage_suffix)
#     router_name = _config_get('router-name', required=True, suffix=storage_suffix)
#     if not routers_manager.get_backend_url_routes(backend_url_target_id):
#         deployment_name = _get_resource_name(suffix=storage_suffix)
#         namespace = _get_namespace()
#         subdomain_route = {
#             'target-type': 'backend-url',
#             'target-resource-id': backend_url_target_id,
#             'backend-url': f'http://{deployment_name}.{namespace}:9000',
#         }
#         if dry_run:
#             logs.info('create_subdomain_route', router_name, subdomain_route)
#         else:
#             routers_manager.create_subdomain_route(router_name, subdomain_route)
#     if not dry_run:
#         routers_manager.update(router_name, wait_ready=True)


def _get_namespace():
    return 'default'


# def _get_frontend_hostname(storage_suffix=None):
#     backend_url_target_id = _get_backend_url_target_id(storage_suffix=storage_suffix)
#     routes = routers_manager.get_backend_url_routes(backend_url_target_id)
#     assert storage_suffix or len(routes) == 1
#     if len(routes) < 1:
#         return 'localhost:9000'
#     else:
#         return routers_manager.get_route_frontend_hostname(routes[0])


# def _get_backend_url_target_id(storage_suffix=None):
#     return f'minio-{storage_suffix}' if storage_suffix else 'minio'
