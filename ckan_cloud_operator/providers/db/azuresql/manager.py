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
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)

################################
# custom provider code starts here
#

import datetime
import os
import yaml
import subprocess
import json

from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize(db_prefix=None, interactive=False):
    _set_provider()
    default_values = {
        'azuresql-instance-name': '',
        'azuresql-host': '',
        'admin-user': '',
        'admin-password': ''
    }
    if interactive:
        print("\n"
              "Starting interactive initialization of the Azure SQL db provider\n"
              "Please prepare the following values:\n"
              "\n"
              " - admin db host and credentials\n"
              " - SQL instance name\n"
              "\n")
        _config_interactive_set(default_values, **_get_config_credentials_kwargs(db_prefix))
    config = _config_get(**_get_config_credentials_kwargs(db_prefix))
    for key, default_value in default_values.items():
        if key not in config and default_value:
            _config_set(key, default_value, **_get_config_credentials_kwargs(db_prefix))
        elif not config.get(key):
            raise Exception(f'missing key: {key}')
    from ckan_cloud_operator.providers.db.proxy.azuresql import manager as proxy_azuresql_manager
    proxy_azuresql_manager.initialize(db_prefix=db_prefix)


def _get_config_credentials_kwargs(db_prefix):
    return {
        'is_secret': True,
        'suffix': f'{db_prefix}-credentials' if db_prefix else 'credentials'
    }


def is_private_ip():
    return False


def get_postgres_admin_credentials(db_prefix=None):
    credentials = _credentials_get(db_prefix)
    return credentials['admin-user'], credentials['admin-password'], credentials.get('admin-db-name', credentials['admin-user'])


def _credentials_get(db_prefix, key=None, default=None, required=False):
    return _config_get(key=key, default=default, required=required, **_get_config_credentials_kwargs(db_prefix))


def get_postgres_external_host_port(db_prefix=None):
    config = _config_get(**_get_config_credentials_kwargs(db_prefix))
    return config['azuresql-host'], 5432


def get_postgres_internal_host_port(db_prefix=None):
    return get_postgres_external_host_port(db_prefix)
