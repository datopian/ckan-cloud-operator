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

import binascii
import json
import os
import subprocess
import yaml

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl


def initialize(interactive=False):
    _set_provider()
    if interactive:
        print('\nEnter the Resource Group name\n')
        _config_interactive_set({'azure-rg': None}, is_secret=False)
        print('\nEnter the location of the Kubernets cluster is hosted on [westus2]\n')
        _config_interactive_set({'azure-default-location': None}, is_secret=False)
        print('\nEnter the name of your cluster\n')
        _config_interactive_set({'azure-cluster-name': None}, is_secret=False)
    else:
        logs.info('Skipping initial cluster set up as `--interactive` flag was not set')


def get_info(debug=False):
    cluster_name = _config_get('cluster-name')
    data = yaml.load(az_check_output(f'container clusters describe {cluster_name}'))
    if debug:
        return data
    else:
        return {
            'name': data['name'],
            'status': data['status'],
            'zone': data['zone'],
            'locations': data['locations'],
            'endpoint': data['endpoint'],
            'nodePools': [
                {
                    'name': pool['name'],
                    'status': pool['status'],
                    'version': pool['version'],
                    'config': {
                        'diskSizeGb': pool['config']['diskSizeGb'],
                        'machineType': pool['config']['machineType'],
                    },
                } for pool in data['nodePools']
            ],
            'createTime': data['createTime'],
            'currentMasterVersion': data['currentMasterVersion'],
            'currentNodeCount': data['currentNodeCount'],
        }


def get_name():
    return _config_get('cluster-name')


def get_cluster_kubeconfig_spec():
    cluster_name = _config_get('cluster-name')
    cluster = yaml.load(az_check_output(f'container clusters describe {cluster_name}'))
    return {
        "server": 'https://' + cluster['endpoint'],
        "certificate-authority-data": cluster['masterAuth']['clusterCaCertificate']
    }


def get_project_zone():
    return _config_get('project-id'), _config_get('cluster-compute-zone')


def create_volume(disk_size_gb, labels, use_existing_disk_name=None):
    rg = _config_get('azure-rg')
    location = _config_get('azure-default-location')

    disk_id = use_existing_disk_name or 'cc' + _generate_password(12)
    if use_existing_disk_name:
        logs.info(f'using existing persistent disk {disk_id}')
    else:
        logs.info(f'creating persistent disk {disk_id} with size {disk_size_gb}GB')
        _, zone = get_project_zone()
        labels = ','.join([
            '{}={}'.format(k.replace('/', '_'), v.replace('/', '_')) for k, v in labels.items()
        ])

    kubectl.apply({
        "kind": "PersistentVolumeClaim",
        "apiVersion": "v1",
        "metadata": {
            "name": disk_id,
            "namespace": "ckan-cloud"
        },
        "spec": {
            "accessModes": [
                "ReadWriteOnce"
            ],
            "resources": {
                "requests": {
                    "storage": f'{disk_size_gb}G'
                }
            },
            "storageClassName": "cca-ckan"
        }
    })
    return {'persistentVolumeClaim': {'claimName': disk_id}}


def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()


def az_check_output(cmd):
    return subprocess.az_check_output(f'az {cmd}', shell=True)
