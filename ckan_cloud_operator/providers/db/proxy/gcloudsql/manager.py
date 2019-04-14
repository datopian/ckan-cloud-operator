#### standard provider code ####

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
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)
def _config_get_volume_spec(volume_name, is_secret=False, suffix=None): return providers_manager.config_get_volume_spec(PROVIDER_SUBMODULE, PROVIDER_ID, volume_name, is_secret, suffix)

################################
# custom provider code starts here
#

import os
import subprocess

from distutils.util import strtobool

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.config import manager as config_manager


def initialize(db_prefix=None):
    _apply_service(db_prefix)
    _apply_deployment(db_prefix)
    if not db_prefix:
        _set_provider()
    else:
        _config_interactive_set({
            'port-forwarded-port': '5433'
        }, suffix=db_prefix)
        db_prefixes = _config_get('all-db-prefixes')
        db_prefixes = db_prefixes.split(',') if db_prefixes else []
        if db_prefix not in db_prefixes:
            db_prefixes.append(db_prefix)
            _config_set('all-db-prefixes', ','.join(db_prefixes))


def get_all_db_prefixes():
    prefixes = _config_get('all-db-prefixes')
    if prefixes:
        return prefixes.split(',')
    else:
        return []


def update(**kwargs):
    pass


def get_internal_proxy_host_port(db_prefix=None):
    namespace = cluster_manager.get_operator_namespace_name()
    service_name = _get_resource_name(suffix=db_prefix or '')
    return f'{service_name}.{namespace}', 5432


def get_external_proxy_host_port(db_prefix=None):
    if strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_USE_PROXY', 'y')):
        host, port = get_external_proxy_forwarded_host_port(db_prefix)
    else:
        host, port = None, None
    return host, port


def get_external_proxy_forwarded_host_port(db_prefix=None):
    return '127.0.0.1', get_port_forwarded_port(db_prefix)


def get_port_forwarded_port(db_prefix=None):
    if db_prefix:
        return _config_get(key='port-forwarded-port', suffix=db_prefix or '')
    else:
        return 5432


def start_port_forward(db_prefix=None):
    """Starts a local proxy to the cloud SQL instance"""
    print("\nKeep this running in the background\n")
    namespace = cluster_manager.get_operator_namespace_name()
    deployment_name = _get_resource_name(suffix=db_prefix or '')
    port = get_port_forwarded_port(db_prefix)
    subprocess.check_call(f'kubectl -n {namespace} port-forward deployment/{deployment_name} {port}:5432',
                          shell=True)


def _apply_deployment(db_prefix=None):
    config = config_manager.get(configmap_name='ckan-cloud-provider-cluster-gcloud')
    project_id = config['project-id']
    location = '-'.join(config['cluster-compute-zone'].split('-')[:2])
    if db_prefix:
        db_config = config_manager.get(secret_name=f'ckan-cloud-provider-db-gcloudsql-{db_prefix}-credentials')
    else:
        db_config = config_manager.get(secret_name='ckan-cloud-provider-db-gcloudsql-credentials')
    db_instance_name = db_config['gcloud-sql-instance-name']
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(suffix=db_prefix),
        _get_resource_labels(for_deployment=True, suffix=db_prefix or ''),
        {
            'replicas': 1,
            'revisionHistoryLimit': 10,
            'strategy': {'type': 'RollingUpdate', },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True, suffix=db_prefix or ''),
                    'annotations': _get_resource_annotations(suffix=db_prefix or '')
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'proxy',
                            'image': 'gcr.io/cloudsql-docker/gce-proxy:1.11',
                            'args': [
                                '/cloud_sql_proxy', f'-instances={project_id}:{location}:{db_instance_name}=tcp:5432'
                            ],
                            'env': [
                                {
                                    'name': 'GOOGLE_APPLICATION_CREDENTIALS',
                                    'value': '/infra/creds.json'
                                }
                            ],
                            'ports': [{'containerPort': 5432}],
                            'volumeMounts': [
                                {
                                    'name': 'service-account',
                                    'mountPath': '/infra/creds.json',
                                    'readOnly': True,
                                    'subPath': 'service-account-json'
                                },
                            ],
                            'resources': {
                                'limits': {
                                    'memory': '1Gi',
                                },
                                'requests': {
                                    'cpu': '0.1',
                                    'memory': '0.2Gi',
                                }
                            }
                        }
                    ],
                    'volumes': [
                        {
                            'name': 'service-account',
                            'secret': {
                                'secretName': 'ckan-cloud-provider-cluster-gcloud',
                            }
                        }
                    ]
                }
            }
        }
    ))


def _apply_service(db_prefix=None):
    deployment_app = _get_resource_labels(for_deployment=True, suffix=db_prefix or '')['app']
    kubectl.apply(kubectl.get_service(
        _get_resource_name(suffix=db_prefix or ''),
        _get_resource_labels(suffix=db_prefix or ''),
        [5432],
        {'app': deployment_app}
    ))
