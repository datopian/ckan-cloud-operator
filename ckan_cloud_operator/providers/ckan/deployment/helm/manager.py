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
import datetime
import time
import json

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac as kubectl_rbac_driver
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.helm import driver as helm_driver
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers.solr import manager as solr_manager
from ckan_cloud_operator.annotations import manager as annotations_manager
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.ckan.constants import INSTANCE_CRD_SINGULAR


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
    if annotations_manager.get_status(instance, 'helm', 'created'):
        values = instance['spec']
    else:
        values = {
            **instance['spec'],
            "replicas": 1,
            "nginxReplicas": 1,
            "disableJobs": True,
            "noProbes": True
        }
    _helm_deploy(
        values, tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version,
        ckan_helm_release_name, instance_id
    )
    _wait_instance_events(instance_id)
    instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id)
    if not annotations_manager.get_status(instance, 'helm', 'created'):
        annotations_manager.set_status(instance, 'helm', 'created')
        _helm_deploy(
            instance['spec'], tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version,
            ckan_helm_release_name, instance_id
        )


def _helm_deploy(values, tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version, ckan_helm_release_name, instance_id):
    with tempfile.NamedTemporaryFile('w') as f:
        yaml.dump(values, f, default_flow_style=False)
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


def get(instance_id, instance=None):
    image = None
    latest_operator_timestamp, latest_pod_name, latest_pod_status = None, None, None
    item_app_statuses = {}
    ckan_deployment_status = None
    ckan_deployment_ready = None
    ckan_deployment_status_pods = []
    all_resources = kubectl.get('all', namespace=instance_id, required=False)
    if len(all_resources.get('items')) > 0:
        for item in all_resources['items']:
            item_kind = item['kind']
            if item_kind in ["Pod", "Deployment", "ReplicaSet"]:
                item_app = item["metadata"]["labels"]["app"]
            elif item_kind == "Service":
                item_app = item["metadata"]["name"]
            else:
                item_app = None
            if item_app in ["ckan", "jobs-db", "redis", "nginx", "jobs"]:
                app_status = item_app_statuses.setdefault(item_app, {})
            else:
                app_status = item_app_statuses.setdefault("unknown", {})
            item_status = kubectl.get_item_detailed_status(item)
            app_status.setdefault("{}s".format(item_kind.lower()), []).append(item_status)
            if item_app == 'ckan' and item_kind == 'Deployment':
                ckan_deployment_status = item_status
                ckan_deployment_ready = len(item_status.get('error', [])) == 0
            if item_app == 'ckan' and item_kind == 'Pod':
                pod = item
                pod_status = item_status
                pod_operator_timestamp = pod['metadata']['creationTimestamp']
                if not latest_operator_timestamp or latest_operator_timestamp < pod_operator_timestamp:
                    latest_operator_timestamp = pod_operator_timestamp
                    latest_pod_name = pod['metadata']['name']
                for container in ["secrets", "ckan"]:
                    status_code, output = subprocess.getstatusoutput(
                        f'kubectl -n {instance_id} logs {pod["metadata"]["name"]} -c {container}',
                    )
                    container_logs = output if status_code == 0 else None
                    if container == 'ckan':
                        pod_status['logs'] = output
                    if container_logs:
                        for logline in container_logs.split("--START_CKAN_CLOUD_LOG--")[1:]:
                            logdata = json.loads(logline.split("--END_CKAN_CLOUD_LOG--")[0])
                            pod_status.setdefault("ckan-cloud-logs", []).append(logdata)
                if not image:
                    image = pod["spec"]["containers"][0]["image"]
                else:
                    if image != pod["spec"]["containers"][0]["image"]:
                        ckan_deployment_ready = False
                        image = pod["spec"]["containers"][0]["image"]
                ckan_deployment_status_pods.append(pod_status)
                if latest_pod_name == pod_status['name']:
                    latest_pod_status = pod_status
        if not latest_pod_status or len(latest_pod_status.get('errors', [])) > 0 or latest_pod_status['logs'] is None:
            ckan_deployment_ready = False
    else:
        ckan_deployment_ready = False
    return {
        **ckan_deployment_status,
        'ready': ckan_deployment_ready,
        'pods': ckan_deployment_status_pods,
        'image': image,
        'latest_pod_name': latest_pod_name,
        'latest_operator_timestamp': latest_operator_timestamp,
        'helm_app_statuses': item_app_statuses,
        'helm_metadata': {
            'ckan_instance_id': instance_id,
            'namespace': instance_id,
            'status_generated_at': datetime.datetime.now(),
            'status_generated_from': subprocess.check_output(["hostname"]).decode().strip(),
        }
    }


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


def _check_instance_events(instance_id):
    status = get(instance_id)
    errors = []
    ckan_cloud_logs = []
    ckan_cloud_events = set()
    pod_names = []
    for app, app_status in status.get('helm_app_statuses', {}).items():
        for kind, kind_items in app_status.items():
            for item in kind_items:
                for error in item.get("errors", []):
                    errors.append(dict(error, kind=kind, app=app, name=item.get("name")))
                for logdata in item.get("ckan-cloud-logs", []):
                    ckan_cloud_logs.append(dict(logdata, kind=kind, app=app, name=item.get("name")))
                    if "event" in logdata:
                        ckan_cloud_events.add(logdata["event"])
                if kind == "pods":
                    pod_names.append(item["name"])
    instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id)
    if annotations_manager.get_status(instance, 'helm', 'created'):
        expected_events = {
            "ckan-env-vars-exists", "ckan-secrets-exists", "got-ckan-secrets",
            "ckan-entrypoint-initialized", "ckan-entrypoint-db-init-success",
            "ckan-entrypoint-extra-init-success"
        }
    else:
        expected_events = {
            "ckan-env-vars-created", "ckan-secrets-created", "got-ckan-secrets", "ckan-db-initialized",
            "ckan-datastore-db-initialized", "ckan-entrypoint-initialized", "ckan-entrypoint-db-init-success",
            "ckan-entrypoint-extra-init-success"
        }
    return expected_events.difference(ckan_cloud_events)


def _wait_instance_events(instance_id):
    start_time = datetime.datetime.now()
    while True:
        time.sleep(15)
        if len(_check_instance_events(instance_id)) == 0:
            break
        if (datetime.datetime.now() - start_time).total_seconds() > 600:
            raise Exception('time out waiting for instance events')
