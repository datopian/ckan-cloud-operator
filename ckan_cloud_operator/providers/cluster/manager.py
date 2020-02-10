import yaml
import subprocess
import binascii
import os
import sys

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.labels import manager as labels_manager

from .constants import OPERATOR_NAMESPACE, OPERATOR_CONFIGMAP


def get_operator_version(verify=False):
    installed_image_tag = _get_installed_operator_image_tag()
    if verify:
        expected_image_tag = _get_expected_operator_image_tag()
        if not expected_image_tag:
            logs.info('No configmap created yet')
            return 'not-configured'
        if installed_image_tag and len(installed_image_tag) >= 2:
            assert installed_image_tag == expected_image_tag, \
                f'installed tag mismatch (expected={expected_image_tag}, actual={installed_image_tag})'
        else:
            logs.error("No version tag could be found. for local development, "
                       "make sure you use correct version and run the following "
                       "to create the file with correct version:\n\n"
                       f"echo {expected_image_tag} | sudo tee /etc/CKAN_CLOUD_OPERATOR_IMAGE_TAG\n")
            logs.exit_catastrophic_failure()
    return installed_image_tag


def print_info(debug=False, minimal=False):
    print(yaml.dump([dict(
        get_kubeconfig_info(),
        nodes=get_node_names(),
    )], default_flow_style=False))
    if not minimal:
        from ckan_cloud_operator.providers import manager as providers_manager
        print(yaml.dump([providers_manager.get_provider('cluster').get_info(debug=debug)], default_flow_style=False))
        if debug:
            assert all([
                subprocess.call(f'kubectl cluster-info', shell=True) == 0,
                subprocess.call(f'kubectl config get-contexts $(kubectl config current-context)', shell=True) == 0,
                subprocess.call(f'kubectl get nodes', shell=True) == 0
            ]), 'failed to get all debug info'
        else:
            return True


def initialize(log_kwargs=None, interactive=False, default_cluster_provider=None, skip_to=None):
    if interactive:
        logs.info('Starting interactive initialization of the operator on the following cluster:')
        print_info(minimal=True)
        if sys.stdout.isatty():
            input('Verify you are connected to the right cluster and press <RETURN> to continue')

    if not skip_to:
        logs.info(f'Creating operator namespace: {OPERATOR_NAMESPACE}', **(log_kwargs or {}))
        subprocess.call(f'kubectl create ns {OPERATOR_NAMESPACE}', shell=True)
        assert default_cluster_provider in ['gcloud', 'aws', 'azure', 'minikube'], f'invalid cluster provider: {default_cluster_provider}'
        subprocess.call(f'kubectl -n {OPERATOR_NAMESPACE} create secret generic ckan-cloud-provider-cluster-{default_cluster_provider}', shell=True)
        subprocess.call(f'kubectl -n {OPERATOR_NAMESPACE} create configmap operator-conf --from-literal=ckan-cloud-operator-image=viderum/ckan-cloud-operator:latest --from-literal=label-prefix={OPERATOR_NAMESPACE}', shell=True)

    from ckan_cloud_operator.providers import manager as providers_manager
    from ckan_cloud_operator.labels import manager as labels_manager
    from ckan_cloud_operator.crds import manager as crds_manager
    from ckan_cloud_operator.providers.db import manager as db_manager
    from ckan_cloud_operator.providers.ckan import manager as ckan_manager
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    from ckan_cloud_operator.providers.solr import manager as solr_manager
    from ckan_cloud_operator.providers.storage import manager as storage_manager
    from ckan_cloud_operator.providers.apps import manager as apps_manager

    for component, func in (
            ('labels', lambda lk: labels_manager.initialize(log_kwargs=lk)),
            ('cluster', lambda lk: providers_manager.get_provider('cluster', default=default_cluster_provider).initialize(interactive=interactive)),
            ('crds', lambda lk: crds_manager.initialize(log_kwargs=lk)),
            ('db', lambda lk: db_manager.initialize(log_kwargs=lk, interactive=interactive, default_cluster_provider=default_cluster_provider)),
            ('routers', lambda lk: routers_manager.initialize(interactive=interactive)),
            ('solr', lambda lk: solr_manager.initialize(interactive=interactive)),
            ('storage', lambda lk: storage_manager.initialize(interactive=interactive)),
            ('ckan', lambda lk: ckan_manager.initialize(interactive=interactive)),
            ('apps', lambda lk: apps_manager.initialize(interactive=interactive)),
    ):
        if not skip_to or skip_to == component:
            skip_to = None
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
    try:
        client_major = int(version['clientMajor'])
    except Exception:
        raise Exception(f'Failed to get kubectl client major version (clientMajor={version["clientMajor"]}')
    client_minor = version['clientMinor']
    if client_minor.endswith('+'):
        client_minor = int(client_minor[:-1])
    else:
        client_minor = int(client_minor)
    assert client_major == 1 and client_minor >= 11, 'Invalid kubectl client version, ' \
                                                     'minimal supported version: 1.11\n' \
                                                     'If you are using GKE, run: gcloud components update'
    try:
        server_major = int(version['serverMajor'])
    except Exception:
        raise Exception(f'Failed to get Kubernetes server major version (serverMajor={version["serverMajor"]}')
    server_minor = version['serverMinor']
    if server_minor.endswith('+'):
        server_minor = int(server_minor[:-1])
    else:
        server_minor = int(server_minor)
    assert server_major == 1 and server_minor >= 10, "Invalid Kubernetes server version, " \
                                                     "minimal supported version: 1.10"
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
    from ckan_cloud_operator.providers import manager as providers_manager
    return providers_manager.get_provider('cluster').get_name()


def get_cluster_kubeconfig_spec():
    from ckan_cloud_operator.providers import manager as providers_manager
    return providers_manager.get_provider('cluster').get_cluster_kubeconfig_spec()


def get_provider():
    from ckan_cloud_operator.providers import manager as providers_manager
    return providers_manager.get_provider('cluster')


def get_provider_id():
    from ckan_cloud_operator.providers import manager as providers_manager
    return providers_manager.get_provider_id('cluster', default='gcloud')


def create_volume(disk_size_gb, labels, use_existing_disk_name=None, zone=0):
    assert len(labels) > 0, 'must provide some labels to identify the volume'
    labels = dict(
        labels,
        **labels_manager.get_resource_labels(label_suffixes=_get_cluster_volume_label_suffixes())
    )
    return get_provider().create_volume(disk_size_gb, labels, use_existing_disk_name=use_existing_disk_name, zone=zone)


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
                'accessModes': ['ReadWriteOnce' if get_provider_id() == 'azure' else 'ReadWriteMany'],
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


def provider_exec(cmd):
    get_provider().exec(cmd)


def setup_autoscaler(expander='random', min_nodes=1, max_nodes=10, zone='', node_pool='default-pool'):
    from ckan_cloud_operator.drivers.helm import driver as helm_driver
    from ckan_cloud_operator.providers import manager as providers_manager

    cloud_provider = get_provider_id()
    cluster_name = kubectl.check_output('config current-context').decode().replace('\n', '')

    if cloud_provider == 'gcloud':
        """GKE has built-in autoscaler"""
        from ckan_cloud_operator import gcloud

        gcloud.check_call(f'container clusters update {cluster_name} --enable-autoscaling --min-nodes {min_nodes} --max-nodes {max_nodes} --zone {zone} --node_pool {node_pool}')
        return

    values = {
        'image.tag': 'v1.13.1',
        'autoDiscovery.clusterName': cluster_name,
        'extraArgs.balance-similar-node-groups': 'false',
        'extraArgs.expander': expander,
        'cloudProvider': cloud_provider,
        'rbac.create': 'true'
    }
    if values['cloudProvider'] == 'aws':
        zone = providers_manager.get_provider('cluster').get_info().get('zone')
        while not zone:
            zone = input('Enter the AWS cluster region: ')
        values['awsRegion'] = zone.strip()

    helm_driver.deploy(
        tiller_namespace='kube-system',
        chart_repo='https://kubernetes-charts.storage.googleapis.com',
        chart_name='stable/cluster-autoscaler',
        chart_version='',
        release_name='cluster-autoscaler',
        namespace='kube-system',
        chart_repo_name='stable',
        values=values
    )

def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()


def _get_cluster_volume_label_suffixes():
    return {'provider-cluster-volume': 'multi-user'}


def _get_installed_operator_image_tag():
    if os.path.exists('/etc/CKAN_CLOUD_OPERATOR_IMAGE_TAG'):
        with open('/etc/CKAN_CLOUD_OPERATOR_IMAGE_TAG') as f:
            return f.read().strip()
    else:
        return None


def _get_expected_operator_image_tag():
    from ckan_cloud_operator.config import manager as config_manager
    expected_image = config_manager.get('ckan-cloud-operator-image')
    if not expected_image:
        return
    assert '@' not in expected_image and ':' in expected_image, f'invalid expected image: {expected_image}'
    _, expected_image_tag = expected_image.split(':')
    return expected_image_tag
