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
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)

################################
# custom provider code starts here
#

import datetime
import os
import yaml
import subprocess
import json

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize(db_prefix=None, interactive=False):
    _set_provider()
    default_values = {
        'host': _get_resource_name(suffix=db_prefix) + '.ckan-cloud',
        'port': '5432',
        'is-private-ip': 'true',
        'admin-user': 'postgres',
        'admin-password': 'postgres',
    }
    config = _config_get(**_get_config_credentials_kwargs(db_prefix))
    for key, default_value in default_values.items():
        if key not in config and default_value:
            _config_set(key, default_value, **_get_config_credentials_kwargs(db_prefix))
        elif not config.get(key):
            raise Exception(f'missing key: {key}')
    _apply_service(db_prefix)
    _apply_deployment(db_prefix)


def get_postgres_internal_host_port(db_prefix=None):
    host = _credentials_get(db_prefix, key='host', required=True)
    port = int(_credentials_get(db_prefix, key='port', required=True))
    return host, port


def get_postgres_external_host_port(db_prefix=None):
    if os.environ.get('CKAN_CLOUD_OPERATOR_USE_PROXY') != 'n':
        assert _credentials_get(db_prefix, key='is-private-ip', required=False) != 'y', 'direct access to the DB is not supported, please enable the db proxy'
    host, port = get_postgres_internal_host_port(db_prefix)
    return host, port


def get_postgres_admin_credentials(db_prefix=None):
    credentials = _credentials_get(db_prefix)
    return credentials['admin-user'], credentials['admin-password'], credentials.get('admin-db-name', credentials['admin-user'])


def is_private_ip(db_prefix=None):
    return _credentials_get(db_prefix, key='is-private-ip', required=False) == 'y'


def _credentials_get(db_prefix, key=None, default=None, required=False):
    return _config_get(key=key, default=default, required=required, **_get_config_credentials_kwargs(db_prefix))


def _get_config_credentials_kwargs(db_prefix):
    return {
        'is_secret': True,
        'suffix': f'{db_prefix}-credentials' if db_prefix else 'credentials'
    }



def _apply_deployment(db_prefix=None):
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(suffix=db_prefix),
        _get_resource_labels(for_deployment=True, suffix=db_prefix or ''),
        {
            'replicas': 1,
            'revisionHistoryLimit': 10,
            'strategy': {'type': 'RollingUpdate', },
            'selector': {
                'matchLabels': _get_resource_labels(for_deployment=True, suffix=db_prefix or '')
            },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True, suffix=db_prefix or ''),
                    'annotations': _get_resource_annotations(suffix=db_prefix or '')
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'postgres',
                            'image': 'mdillon/postgis',
                            'env': [
                                {
                                    'name': 'POSTGRES_PASSWORD',
                                    'value': 'postgres'
                                },
                                {
                                    'name': 'POSTGRES_USER',
                                    'value': 'postgres'
                                },
                            ],
                            'ports': [{'containerPort': 5432}],
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
