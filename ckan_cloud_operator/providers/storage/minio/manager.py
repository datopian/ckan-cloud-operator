#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
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

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers import manager as routers_manager


def initialize(interactive=False):
    _config_interactive_set({
        'disk-size-gb': None,
        'router-name': routers_manager.get_default_infra_router_name()
    }, interactive=interactive)
    _apply_secret()
    _apply_deployment(_get_or_create_volume())
    _apply_service()
    _update_route()
    _set_provider()


def print_credentials(raw=False):
    hostname, access_key, secret_key = get_credentials()
    if raw:
        print(f'https://{hostname} {access_key} {secret_key}')
    else:
        print('Minio admin credentials:')
        print('External Domain: ' + hostname)
        print('Access Key: ' + access_key)
        print('Secret Key: ' + secret_key)
        print('\nto use with minio-client, run the following command:')
        print(f'mc config host add ckan-edge https://{hostname} {access_key} {secret_key}')



def get_credentials():
    return [_get_frontend_hostname()] + [
        _config_get(key, required=True, is_secret=True)
        for key in ['MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY']
    ]


def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()


def _apply_secret():
    access_key = _config_get('MINIO_ACCESS_KEY', required=False, is_secret=True) or _generate_password(8)
    secret_key = _config_get('MINIO_SECRET_KEY', required=False, is_secret=True) or _generate_password(12)
    _config_set(values={'MINIO_ACCESS_KEY': access_key, 'MINIO_SECRET_KEY': secret_key}, is_secret=True)


def _apply_deployment(volume_spec):
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(),
        _get_resource_labels(for_deployment=True),
        {
            'replicas': 1,
            'revisionHistoryLimit': 10,
            'strategy': {'type': 'Recreate', },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True),
                    'annotations': _get_resource_annotations()
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'minio',
                            'image': 'minio/minio',
                            'args': ['server', '/export'],
                            'envFrom': [{'secretRef': {'name': _get_resource_name()}}],
                            'ports': [{'containerPort': 9000}],
                            'volumeMounts': [
                                {
                                    'name': 'minio-data',
                                    'mountPath': '/export',
                                }
                            ],
                        }
                    ],
                    'volumes': [
                        dict(volume_spec, name='minio-data')
                    ]
                }
            }
        }
    ))


def _apply_service():
    kubectl.apply(kubectl.get_resource(
        'v1', 'Service',
        _get_resource_name(),
        _get_resource_labels(),
        spec={
            'ports': [
                {'name': '9000', 'port': 9000}
            ],
            'selector': {
                'app': _get_resource_labels(for_deployment=True)['app']
            }
        }
    ))


def _get_or_create_volume():
    disk_size_gb = _config_get('disk-size-gb', required=True)
    volume_spec = _config_get('volume-spec', required=False)
    if volume_spec:
        volume_spec = yaml.load(volume_spec)
    else:
        from ckan_cloud_operator.providers.cluster import manager as cluster_manager
        volume_spec = cluster_manager.create_volume(disk_size_gb, _get_resource_labels())
        _config_set('volume-spec', yaml.dump(volume_spec, default_flow_style=False))
    return volume_spec


def _update_route():
    backend_url_target_id = 'minio'
    router_name = _config_get('router-name', required=True)
    if not routers_manager.get_backend_url_routes(backend_url_target_id):
        deployment_name = _get_resource_name()
        namespace = _get_namespace()
        routers_manager.create_subdomain_route(
            router_name,
            {
                'target-type': 'backend-url',
                'target-resource-id': backend_url_target_id,
                'backend-url': f'http://{deployment_name}.{namespace}:9000',
            }
        )
    routers_manager.update(router_name, wait_ready=True)


def _get_namespace():
    return 'ckan-cloud'


def _get_frontend_hostname():
    routes = routers_manager.get_backend_url_routes('minio')
    assert len(routes) == 1
    return routers_manager.get_route_frontend_hostname(routes[0])
