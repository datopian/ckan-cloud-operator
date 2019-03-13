import yaml
import subprocess
import binascii
import os

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator.labels import manager as labels_manager

from .constants import OPERATOR_NAMESPACE, OPERATOR_CONFIGMAP


def print_info(debug=False, minimal=False):
    print(yaml.dump([dict(get_kubeconfig_info(), nodes=get_node_names())], default_flow_style=False))
    if not minimal:
        print(yaml.dump([providers_manager.get_provider('cluster').get_info(debug=debug)], default_flow_style=False))
        if debug:
            assert all([
                subprocess.call(f'kubectl cluster-info', shell=True) == 0,
                subprocess.call(f'kubectl config get-contexts $(kubectl config current-context)', shell=True) == 0,
                subprocess.call(f'kubectl get nodes', shell=True) == 0
            ]), 'failed to get all debug info'
        else:
            return True


def initialize(log_kwargs=None, interactive=False):
    if interactive:
        logs.info('Starting interactive initialization of the operator on the following cluster:')
        print_info(minimal=True)
        input('Verify your are connected to the right cluster and press <RETURN> to continue')
    logs.info(f'Creating operator namespace: {OPERATOR_NAMESPACE}', **(log_kwargs or {}))
    subprocess.call(f'kubectl create ns {OPERATOR_NAMESPACE}', shell=True)

    from ckan_cloud_operator.labels import manager as labels_manager
    from ckan_cloud_operator.crds import manager as crds_manager
    from ckan_cloud_operator.providers.db import manager as db_manager
    from ckan_cloud_operator.providers.ckan import manager as ckan_manager
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    from ckan_cloud_operator.providers.solr import manager as solr_manager
    from ckan_cloud_operator.providers.storage import manager as storage_manager

    for component, func in (
            ('labels', lambda lk: labels_manager.initialize(log_kwargs=lk)),
            ('cluster', lambda lk: providers_manager.get_provider('cluster', default='gcloud').initialize(interactive=interactive)),
            ('crds', lambda lk: crds_manager.initialize(log_kwargs=lk)),
            ('db', lambda lk: db_manager.initialize(log_kwargs=lk, interactive=interactive)),
            ('routers', lambda lk: routers_manager.initialize(interactive=interactive)),
            ('solr', lambda lk: solr_manager.initialize(interactive=interactive)),
            ('storage', lambda lk: storage_manager.initialize(interactive=interactive)),
            ('ckan', lambda lk: ckan_manager.initialize(interactive=interactive)),
    ):
        log_kwargs = {'cluster-init': component}
        logs.info(f'Initializing', **log_kwargs)
        func(log_kwargs)


def get_kubeconfig_info():
    kubeconfig = kubectl.get('config view', get_cmd='')
    clusters = kubeconfig['clusters']
    num_clusters = len(clusters)
    assert num_clusters == 1, f'Invalid number of clusters in kubeconfig: {num_clusters}'
    cluster = clusters[0]
    contexts = kubeconfig['contexts']
    num_contexts = len(contexts)
    assert num_contexts == 1, f'Invalid number of contexts in kubeconfig: {num_contexts}'
    context = contexts[0]
    return {
        'name': cluster['name'],
        'server': cluster['cluster']['server'],
        'user': context['context']['user'],
        **get_kube_version_info(),
    }


def get_kube_version_info():
    version = kubectl.get('', get_cmd='version')
    version = {
        'clientMajor': version['clientVersion']['major'],
        'clientMinor': version['clientVersion']['minor'],
        'serverMajor': version['serverVersion']['major'],
        'serverMinor': version['serverVersion']['minor'],
    }
    assert int(version['clientMajor']) == 1 and int(version['clientMinor']) >= 11, 'Invalid kubectl client version, ' \
                                                                                   'minimal supported version: 1.11\n' \
                                                                                   'If you are using GKE, run: gcloud components update'
    return version


def get_node_names():
    return kubectl.check_output('get nodes -o custom-columns=name:.metadata.name --no-headers').decode().splitlines()


def get_operator_namespace_name():
    return OPERATOR_NAMESPACE


def get_operator_configmap_name():
    return OPERATOR_CONFIGMAP


def get_operator_configmap_namespace_defaults(configmap_name=None, namespace=None):
    return (configmap_name or get_operator_configmap_name()), (namespace or get_operator_namespace_name())


def get_cluster_name():
    return providers_manager.get_provider('cluster').get_name()


def get_cluster_kubeconfig_spec():
    return providers_manager.get_provider('cluster').get_cluster_kubeconfig_spec()


def get_provider():
    return providers_manager.get_provider('cluster')


def create_volume(disk_size_gb, labels, use_existing_disk_name=None):
    assert len(labels) > 0, 'must provide some labels to identify the volume'
    labels = dict(
        labels,
        **labels_manager.get_resource_labels(label_suffixes=_get_cluster_volume_label_suffixes())
    )
    return get_provider().create_volume(disk_size_gb, labels, use_existing_disk_name=use_existing_disk_name)


def get_or_create_multi_user_volume_claim(label_suffixes):
    assert len(label_suffixes) > 0, 'must provide some labels to identify the volume'
    claim_labels = labels_manager.get_resource_labels(label_suffixes=dict(
        label_suffixes, **_get_cluster_volume_label_suffixes()
    ))
    pvcs = kubectl.get_items_by_labels('PersistentVolumeClaim', claim_labels, required=False)
    if len(pvcs) > 0:
        assert len(pvcs) == 1
        claim_name = pvcs[0]['metadata']['name']
    else:
        storage_class_name = get_multi_user_storage_class_name()
        claim_name = 'cc' + _generate_password(12)
        logs.info(f'Creating persistent volume claim: {claim_name}')
        logs.info(f'labels: {claim_labels}')
        kubectl.apply(kubectl.get_persistent_volume_claim(
            claim_name,
            claim_labels,
            {
                'storageClassName': storage_class_name,
                'accessModes': ['ReadWriteMany'],
                'resources': {
                    'requests': {
                        'storage': '1Mi'
                    }
                }
            }
        ))
    return {'persistentVolumeClaim': {'claimName': claim_name}}


def get_multi_user_storage_class_name():
    return 'cca-ckan'


def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()


def _get_cluster_volume_label_suffixes():
    return {'provider-cluster-volume': 'multi-user'}
