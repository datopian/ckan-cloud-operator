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

import os
import yaml
import binascii

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl



def initialize(interactive=False):
    _set_provider()
    if interactive:
        print('\nUsing Minikube\n')
    print(yaml.dump(get_info(), default_flow_style=False))
    _create_storage_classes()


def get_info(debug=False):
    return {}

def _create_storage_classes():
    for sc in ('cca-storage', 'cca-ckan'):
        kubectl.apply({
            'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
            'metadata': {
                'annotations': {'storageclass.kubernetes.io/is-default-class': 'true'},
                'labels': {'addonmanager.kubernetes.io/mode': 'EnsureExists'},
                'name': sc,
            },
            'provisioner': 'k8s.io/minikube-hostpath',
            'reclaimPolicy': 'Delete',
            'volumeBindingMode': 'Immediate'
        })



def create_volume(disk_size_gb, labels, use_existing_disk_name=None, zone=None):
    disk_id = use_existing_disk_name or 'cc' + _generate_password(12)
    if use_existing_disk_name:
        logs.info(f'using existing persistent disk {disk_id}')
    else:
        logs.info(f'creating persistent disk {disk_id} with size {disk_size_gb}')
    kubectl.apply({
        'apiVersion': 'v1', 'kind': 'PersistentVolume',
        'metadata': {'name': disk_id, 'namespace': 'ckan-cloud'},
        'spec': {
            'capacity': {'storage': f'{disk_size_gb}G'},
            'accessModes': ['ReadWriteOnce'],
            'hostPath': {'path': '/data/' + disk_id},
            'storageClassName': '',
        }
    })
    kubectl.apply({
        'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
        'metadata': {'name': disk_id, 'namespace': 'ckan-cloud'},
        'spec': {
            'volumeName': disk_id,
            'accessModes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': f'{disk_size_gb}G'}},
            'storageClassName': '',
        }
    })
    return {'persistentVolumeClaim': {'claimName': disk_id}}


def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()
