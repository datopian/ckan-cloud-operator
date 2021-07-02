import yaml
import time
import datetime
import binascii
import os
import traceback
import subprocess
import sys

from ckan_cloud_operator import kubectl, logs, yaml_config
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


import yaml
from pathlib import Path


def list_environments():
    if _cco_is_configured() and _get_config():
        cco_config = _get_config()
        for environment in cco_config.get('environments', []):
            prefix = '>' if environment.get('active', False) else '-'
            print(prefix, environment.get('name'))
    else:
        print('Ckan Cloud Operator is no yet configured. Please run cco add << environment >>')

def add_environment(environment, **kwargs):
    cco_config = {}
    if _cco_is_configured() and _get_config():
        cco_config = _get_config()
        new_envs = [_env for _env in cco_config.get('environments') or [] if environment.lower() != _env.get('name', '').lower()]
        cco_config['environments'] = new_envs

    if kwargs['cloud_provider'] == 'azure':
        _run_az_command_or_login(
            f'az account set --subscription {kwargs["subscription"]}',
            add_environment,
            kwargs
        )
        kwargs['logged_in'] = True
        _run_az_command_or_login(
            f'az aks get-credentials --resource-group {kwargs["resource_group"]} --name {kwargs["cluster_name"]}',
            add_environment,
            kwargs
        )
        envs = cco_config.get('environments', []) or []
        for _env in envs:
            _env['active'] = False
        kwargs['active'] = True
        kwargs['name'] = environment
        envs.append(kwargs)
        cco_config['environments'] = envs
        # update config file
        _mkconfdir()
        _write_yaml(cco_config)
        print(f'{kwargs["cluster_name"]} has been successfully configured for "{environment}" environment')
    elif kwargs['cloud_provider'] == 'gcloud':
        #TODO
        pass
    elif kwargs['cloud_provider'] == 'aws':
        #TODO
        pass
    elif kwargs['cloud_provider'] == 'minio':
        #TODO
        pass
    else:
        logs.warning(f'Cloud Provider "{cloud_provider}" is not supported')

def update_environment(environment, **kwargs):
    updated_envs = []
    cco_config = {}
    if _cco_is_configured() and _get_config():
        cco_config = _get_config()
        env_exists = any([environment.lower() == _env.get('name', '').lower() for _env in cco_config.get('environments') or []])
        if not env_exists:
            logs.info(f'Environment {environment} does not exists. Please run `cco ckan env add` with the same flags')
            return
        envs = cco_config.get('environments', [])

        for _env in envs:
            if _env.get('name').lower() == environment.lower():
                to_update = {k:v for k,v in kwargs.items() if v is not None}
                _env.update(to_update)
            updated_envs.append(_env)
        cco_config['environments'] = updated_envs
    _mkconfdir()
    _write_yaml(cco_config)


def set_environment(environment):
    updated_envs = []
    cco_config = {}
    if _cco_is_configured() and _get_config():
        cco_config = _get_config()
        env_exists = any([environment.lower() == _env.get('name', '').lower() for _env in cco_config.get('environments') or []])
        if not env_exists:
            logs.info(f'Environment {environment} does not exists. Please run `cco ckan env add` with the same flags')
            return
        envs = cco_config.get('environments', [])

        for _env in envs:
            _env['active'] = _env.get('name').lower() == environment.lower()
            if _env['active']:
                add_environment(environment, **_env)
            updated_envs.append(_env)

        cco_config['environments'] = updated_envs
    _mkconfdir()
    _write_yaml(cco_config)



def remove_environment(environment):
    updated_envs = []
    cco_config = {}
    if _cco_is_configured() and _get_config():
        cco_config = _get_config()
        env_exists = any([environment.lower() == _env.get('name', '').lower() for _env in cco_config.get('environments') or []])
        if not env_exists:
            logs.info(f'Environment {environment} does not exists. Please run `cco ckan env add {environment}`')
            return
        envs = cco_config.get('environments', [])

        for _env in envs:
            if _env.get('name').lower() == environment.lower():
                continue
            updated_envs.append(_env)
        cco_config['environments'] = updated_envs
    _mkconfdir()
    _write_yaml(cco_config)


def _cco_is_configured():
    return os.path.isfile(_get_config_file_name())


def _get_config():
    config_file = open(_get_config_file_name())
    return yaml.load(config_file)


def _get_config_file_name():
    return str(os.path.join(Path.home(),'.cco','cco.yaml'))


def _get_config_dir():
    return str(os.path.join(Path.home(),'.cco'))


def _write_yaml(data):
    _file = open(_get_config_file_name(), "w")
    yaml_config.yaml_dump(data, _file)
    _file.close()


def _mkconfdir():
    dir = _get_config_dir()
    Path(f'{dir}').mkdir(parents=True, exist_ok=True)


def _run_az_command_or_login(command, func, *args):
    if not args[-1]:
        logs.subprocess_check_output(['az', 'login'])
        print("Logged in successfully.")
    try:
        logs.subprocess_check_call(command.split(' '))
    except AttributeError as e:
        print('You need to login to azure CLI. Please authenticate with browser.')
        func(*args[:-1], logged_in=False)
