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
