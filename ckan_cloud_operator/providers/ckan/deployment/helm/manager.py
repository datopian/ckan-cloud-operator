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

import yaml
import tempfile
import subprocess
import traceback

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac as kubectl_rbac_driver
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.helm import driver as helm_driver
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers.solr import manager as solr_manager


def initialize():
    tiller_namespace_name = _get_resource_name()
    helm_driver.init(tiller_namespace_name)


def update(instance_id, instance):
    tiller_namespace_name = _get_resource_name()
    _init_namespace(instance_id)
    _init_ckan_infra_secret(instance_id)
    ckan_helm_chart_repo = instance['spec'].get(
        "ckanHelmChartRepo",
        "https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-helm/master/charts_repository"
    )
    ckan_helm_chart_version = instance['spec'].get("ckanHelmChartVersion", "")
    ckan_helm_release_name = f'ckan-cloud-{instance_id}'
    instance['spec']['centralizedSolrHost'], instance['spec']['centralizedSolrPort'] = _init_solr(instance_id)
    with tempfile.NamedTemporaryFile('w') as f:
        yaml.dump(instance['spec'], f, default_flow_style=False)
        f.flush()
        helm_driver.deploy(tiller_namespace_name, ckan_helm_chart_repo, 'ckan-cloud/ckan', ckan_helm_chart_version,
                           ckan_helm_release_name, f.name, instance_id)


def delete(instance_id, instance):
    tiller_namespace_name = _get_resource_name()
    ckan_helm_release_name = f'ckan-cloud-{instance_id}'
    errors = []
    try:
        logs.info(f'Deleting helm release {ckan_helm_release_name}')
        helm_driver.delete(tiller_namespace_name, ckan_helm_release_name)
    except Exception as e:
        logs.warning(traceback.format_exc())
        errors.append(f'Failed to delete helm release')
    if kubectl.call(f'delete --wait=false namespace {instance_id}') != 0:
        errors.append(f'Failed to delete namespace')
    assert len(errors) == 0, ', '.join(errors)


def get(instance_id, instance):
    exitcode, output = subprocess.getstatusoutput(f'kubectl -n {instance_id} get deployment/ckan -o yaml')
    if exitcode == 0:
        deployment = yaml.load(output)
        status = kubectl.get_item_detailed_status(deployment)
        ready = len(status.get('error', [])) == 0
        status['pods'] = []
        pods = kubectl.get('pods -l app=ckan', namespace=instance_id, required=False)
        image = None
        latest_operator_timestamp, latest_pod_name, latest_pod_status = None, None, None
        if pods:
            for pod in pods['items']:
                pod_operator_timestamp = pod['metadata']['creationTimestamp']
                if not latest_operator_timestamp or latest_operator_timestamp < pod_operator_timestamp:
                    latest_operator_timestamp = pod_operator_timestamp
                    latest_pod_name = pod['metadata']['name']
                pod_status = kubectl.get_item_detailed_status(pod)
                status_code, output = subprocess.getstatusoutput(
                    f'kubectl -n {instance_id} logs {pod["metadata"]["name"]} -c ckan --tail 5',
                )
                if status_code == 0:
                    pod_status['logs'] = output
                else:
                    pod_status['logs'] = None
                if not image:
                    image = pod["spec"]["containers"][0]["image"]
                else:
                    if image != pod["spec"]["containers"][0]["image"]:
                        ready = False
                        image = pod["spec"]["containers"][0]["image"]
                status['pods'].append(pod_status)
                if latest_pod_name == pod_status['name']:
                    latest_pod_status = pod_status
            if not latest_pod_status or len(latest_pod_status.get('errors', [])) > 0 or latest_pod_status['logs'] is None:
                ready = False
        else:
            ready = False
        return dict(status, ready=ready, image=image, latest_pod_name=latest_pod_name, latest_operator_timestamp=latest_operator_timestamp)
    else:
        return {'ready': False, 'error': output}


def get_backend_url(instance_id, instance):
    return f'http://nginx.{instance_id}:8080'


def _init_ckan_infra_secret(instance_id):
    ckan_infra = config_manager.get(secret_name='ckan-infra', namespace=instance_id, required=False)
    if ckan_infra:
        print('ckan-infra secret already exists')
    else:
        admin_user, admin_password, db_name = db_manager.get_admin_db_credentials()
        db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
        assert int(db_port) == 5432
        config_manager.set(
            values={
                'POSTGRES_HOST': db_host,
                'POSTGRES_PASSWORD': admin_password,
                'POSTGRES_USER': admin_user
            },
            secret_name='ckan-infra',
            namespace=instance_id
        )


def _init_namespace(instance_id):
    if kubectl.get('ns', instance_id, required=False):
        logs.info(f'instance namespace already exists ({instance_id})')
    else:
        logs.info(f'creating instance namespace ({instance_id})')
        kubectl.apply(kubectl.get_resource('v1', 'Namespace', instance_id, {}))
        kubectl_rbac_driver.update_service_account(f'ckan-{instance_id}-operator', {}, namespace=instance_id)
        kubectl_rbac_driver.update_role(f'ckan-{instance_id}-operator-role', {}, [
            {
                "apiGroups": [
                    "*"
                ],
                "resources": [
                    'secrets', 'pods', 'pods/exec', 'pods/portforward'
                ],
                "verbs": [
                    "list", "get", "create"
                ]
            }
        ], namespace=instance_id)
        kubectl_rbac_driver.update_role_binding(
            name=f'ckan-{instance_id}-operator-rolebinding',
            role_name=f'ckan-{instance_id}-operator-role',
            namespace=instance_id,
            service_account_name=f'ckan-{instance_id}-operator',
            labels={}
        )


def _init_solr(instance_id):
    solr_status = solr_manager.get_collectoin_status(instance_id)
    if not solr_status['ready']:
        solr_manager.create_collection(instance_id, 'ckan_28_default')
    else:
        logs.info(f'collection already exists ({instance_id})')
    solr_url = solr_status['solr_http_endpoint']
    assert solr_url.startswith('http') and solr_url.endswith('/solr'), f'invalid solr_url ({solr_url})'
    host, port = solr_url.replace('https://', '').replace('http://', '').replace('/solr', '').split(':')
    return host, port
