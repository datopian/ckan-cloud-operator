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
import binascii
import os

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac as kubectl_rbac_driver
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.helm import driver as helm_driver
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.ckan import manager as ckan_manager
from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers.solr import manager as solr_manager
from ckan_cloud_operator.annotations import manager as annotations_manager
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.ckan.constants import INSTANCE_CRD_SINGULAR
from ckan_cloud_operator.routers import manager as routers_manager


def initialize(interactive=False):
    tiller_namespace_name = _get_resource_name()
    helm_driver.init(tiller_namespace_name)


def update(instance_id, instance, force=False, dry_run=False):
    tiller_namespace_name = _get_resource_name()
    logs.debug('Updating helm-based instance deployment',
               instance_id=instance_id, tiller_namespace_name=tiller_namespace_name)
    _create_private_container_registry_secret(instance_id)
    _init_ckan_infra_secret(instance_id, dry_run=dry_run)
    ckan_helm_chart_repo = instance['spec'].get(
        "ckanHelmChartRepo",
        "https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-helm/master/charts_repository"
    )
    ckan_helm_chart_version = instance['spec'].get("ckanHelmChartVersion", "")
    ckan_helm_release_name = f'ckan-cloud-{instance_id}'
    solr_schema = instance['spec'].get("ckanSolrSchema", "ckan_default")
    solr_host, solr_port = _init_solr(instance_id, solr_schema, dry_run=dry_run,)
    logs.debug(ckan_helm_chart_repo=ckan_helm_chart_repo,
               ckan_helm_chart_version=ckan_helm_chart_version, ckan_helm_release_name=ckan_helm_release_name,
               solr_host=solr_host, solr_port=solr_port)
    instance['spec']['centralizedSolrHost'], instance['spec']['centralizedSolrPort'] = solr_host, solr_port
    if annotations_manager.get_status(instance, 'helm', 'created'):
        logs.info('Updating existing instance')
        values = instance['spec']
    else:
        logs.info('New instance, deploying first with 1 replica and disabled probes and jobs')
        values = {
            **instance['spec'],
            "replicas": 1,
            "nginxReplicas": 1,
            "disableJobs": True,
            "noProbes": True,
            "enableHarvesterNG": False
        }
    _helm_deploy(
        values, tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version,
        ckan_helm_release_name, instance_id, dry_run=dry_run
    )
    if not dry_run:
        _wait_instance_events(instance_id)
        instance = crds_manager.get(INSTANCE_CRD_SINGULAR, name=instance_id)
        if not annotations_manager.get_status(instance, 'helm', 'created'):
            annotations_manager.set_status(instance, 'helm', 'created')
            _helm_deploy(
                instance['spec'], tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version,
                ckan_helm_release_name, instance_id
            )
            _scale_down_scale_up(namespace=instance_id, replicas=values.get('replicas', 1))


def _helm_deploy(values, tiller_namespace_name, ckan_helm_chart_repo, ckan_helm_chart_version, ckan_helm_release_name,
                 instance_id, dry_run=False):
    logs.debug(f'Deploying helm chart {ckan_helm_chart_repo} {ckan_helm_chart_version} to release {ckan_helm_release_name} (instance_id={instance_id})')
    with tempfile.NamedTemporaryFile('w') as f:
        yaml.dump(values, f, default_flow_style=False)
        f.flush()
        helm_driver.deploy(tiller_namespace_name, ckan_helm_chart_repo, 'ckan-cloud/ckan', ckan_helm_chart_version,
                           ckan_helm_release_name, f.name, instance_id, dry_run=dry_run)


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
    logs.debug('Getting all namespace resources', namespace=instance_id)
    all_resources = kubectl.get('all', namespace=instance_id, required=False)
    num_resource_items = len(all_resources.get('items'))
    logs.debug(num_resource_items=num_resource_items)
    if num_resource_items > 0:
        for item in all_resources['items']:
            item_kind = item['kind']
            try:
                if item_kind in ("Pod", "ReplicaSet"):
                    item_app = item["metadata"]["labels"]["app"]
                elif item_kind in ("Service", "Deployment"):
                    item_app = item["metadata"]["name"]
                else:
                    item_app = None
            except:
                logging.exception('Failed to extract item_app from %r', item)
                item_app = None
            logs.debug(item_kind=item_kind, item_app=item_app)
            if item_app in ["ckan", "jobs-db", "redis", "nginx", "jobs"]:
                app_status = item_app_statuses.setdefault(item_app, {})
            else:
                app_status = item_app_statuses.setdefault("unknown", {})
            item_status = kubectl.get_item_detailed_status(item)
            app_status.setdefault("{}s".format(item_kind.lower()), []).append(item_status)
            if item_app == 'ckan':
                if item_kind == 'Deployment':
                    ckan_deployment_status = item_status
                    ckan_deployment_ready = len(item_status.get('error', [])) == 0
                    logs.debug(ckan_deployment_ready=ckan_deployment_ready)
                elif item_kind == 'Pod':
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
                        logs.debug(len_container_logs=len(container_logs) if container_logs else 0)
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


def pre_update_hook(instance_id, instance, override_spec, skip_route=False, dry_run=False):
    _init_namespace(instance_id, dry_run=dry_run)
    _pre_update_hook_override_spec(override_spec, instance)
    if not instance['spec'].get('useCentralizedInfra'):
        logs.warning('Forcing centralized infra even though useCentralizedInfra is disabled')
        _pre_update_hook_modify_spec(instance_id, instance, lambda i: i.update(useCentralizedInfra=True),
                                     dry_run=dry_run)
    res = {}
    sub_domain, root_domain = _pre_update_hook_route(instance_id, skip_route, instance, res, dry_run=dry_run)
    _pre_update_hook_admin_user(instance, sub_domain, root_domain, instance_id, res, dry_run=dry_run)
    return res


def create_ckan_admin_user(instance_id, instance, user):
    pod_name = None
    while not pod_name:
        try:
            pod_name = kubectl.get_deployment_pod_name('ckan', instance_id, use_first_pod=True, required_phase='Running')
            break
        except Exception as e:
            logs.warning('Failed to find running ckan pod', str(e))
        time.sleep(20)

    name, password, email = [user[k] for k in ['name', 'password', 'email']]
    logs.info(f'Creating CKAN admin user with {name} ({email}) and {password} on pod {pod_name}')
    logs.subprocess_check_call(
        f'echo y | kubectl -n {instance_id} exec -i {pod_name} -- ckan-paster --plugin=ckan sysadmin -c /etc/ckan/production.ini add {name} password={password} email={email}',
        shell=True
    )


def _init_ckan_infra_secret(instance_id, dry_run=False):
    logs.debug('Initializing ckan infra secret', instance_id=instance_id)
    ckan_infra = config_manager.get(secret_name='ckan-infra', namespace=instance_id, required=False)
    if ckan_infra:
        logs.info('ckan-infra secret already exists')
    else:
        admin_user, admin_password, db_name = db_manager.get_admin_db_credentials()
        db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
        assert int(db_port) == 5432
        logs.debug('Creating ckan-infra secret', admin_user=admin_user, admin_password=admin_password, db_name=db_name,
                   db_host=db_host, db_port=db_port)
        config_manager.set(
            values={
                'POSTGRES_HOST': db_host,
                'POSTGRES_PASSWORD': admin_password,
                'POSTGRES_USER': admin_user
            },
            secret_name='ckan-infra',
            namespace=instance_id,
            dry_run=dry_run
        )

def _create_private_container_registry_secret(instance_id):
    if config_manager.get('private-registry', secret_name='ckan-docker-registry') == 'y':
        docker_server, docker_username, docker_password, docker_email = ckan_manager.get_docker_credentials()
        image_pull_secret_name = config_manager.get('docker-image-pull-secret-name', secret_name='ckan-docker-registry')
        subprocess.call(f'kubectl -n {instance_id} create secret docker-registry {image_pull_secret_name} '
                              f'--docker-password={docker_password} '
                              f'--docker-server={docker_server} '
                              f'--docker-username={docker_username} '
                              f'--docker-email={docker_email}', shell=True)


def _init_namespace(instance_id, dry_run=False):
    logs.debug('Initializing helm-based instance deployment namespace', namespace=instance_id)
    if kubectl.get('ns', instance_id, required=False):
        logs.info(f'instance namespace already exists ({instance_id})')
    else:
        logs.info(f'creating instance namespace ({instance_id})')
        kubectl.apply(kubectl.get_resource('v1', 'Namespace', instance_id, {}), dry_run=dry_run)
        service_account_name = f'ckan-{instance_id}-operator'
        logs.debug('Creating service account', service_account_name=service_account_name)
        if not dry_run:
            kubectl_rbac_driver.update_service_account(f'ckan-{instance_id}-operator', {}, namespace=instance_id)
        role_name = f'ckan-{instance_id}-operator-role'
        logs.debug('Creating role and binding to the service account', role_name=role_name)
        if not dry_run:
            kubectl_rbac_driver.update_role(role_name, {}, [
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


def _init_solr(instance_id, solr_schema, dry_run=False):
    logs.debug('Initializing solr', instance_id=instance_id)
    solr_status = solr_manager.get_collection_status(instance_id)
    logs.debug_yaml_dump(solr_status)
    if not solr_status['ready']:
        logs.info('Creating solr collection', collection_name=instance_id, solr_config=solr_schema)
        if not dry_run:
            solr_manager.create_collection(instance_id, solr_schema)
    else:
        logs.info(f'collection already exists ({instance_id})')
    solr_url = solr_status['solr_http_endpoint']
    logs.debug(solr_url=solr_url)
    assert solr_url.startswith('http') and solr_url.endswith('/solr'), f'invalid solr_url ({solr_url})'
    host, port = solr_url.replace('https://', '').replace('http://', '').replace('/solr', '').split(':')
    logs.debug('Solr initialization completed successfully', host=host, port=port)
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
    expected_events = {
        ("ckan-env-vars-created", "ckan-env-vars-exists"),
        ("ckan-secrets-created", "ckan-secrets-exists"),
        "got-ckan-secrets",
        "ckan-entrypoint-initialized",
        "ckan-entrypoint-db-init-success",
        "ckan-entrypoint-extra-init-success"
    }
    missing = set()
    for events in expected_events:
        if isinstance(events, str):
            events = (events,)
        found = False
        for e in events:
            if e in ckan_cloud_events:
                found = True
                break
        if not found:
            missing.add('/'.join(events))
    logs.debug(ckan_cloud_events=ckan_cloud_events)
    return missing, errors, ckan_cloud_logs

def _wait_instance_events(instance_id):
    import logging
    start_time = datetime.datetime.now()
    last_message = 0
    logs.info('Waiting for instance events', start_time=start_time)
    missing_events = None
    while True:
        time.sleep(15)
        currently_missing, errors, ckan_logs = _check_instance_events(instance_id)
        if len(currently_missing) == 0:
            logs.info('All instance events completed successfully')
            break
        if currently_missing != missing_events:
            missing_events = currently_missing
            logs.info('Still waiting for', repr(sorted(missing_events)))
            start_time = datetime.datetime.now()
        time_passed = (datetime.datetime.now() - start_time).total_seconds()
        if time_passed - last_message >= 60:
            logs.info('%d seconds since started waiting' % time_passed)
            last_message += 60
        if time_passed > int(os.environ.get('CCO_WAIT_TIMEOUT', 500)):
            failed_pods = [
                item for item in kubectl.get(f'pods -n {instance_id}').get('items', [])
                    if not all(stat.get('ready') for stat in item['status']['containerStatuses'])
            ]
            logs.info('*** SOMETHING WENT WRONG!!! ***')
            logs.info(100*'#')
            logs.info(100*'#')
            if not len(failed_pods):
                logs.info('But we could not get failing containers')
                logs.info('You may try increasing default wait timeout by setting CCO_WAIT_TIMEOUT environment variable [default: 500]')
                ckan_pod_name = [
                    item['metadata']['name'] for item in kubectl.get(f'pods -n {instance_id}').get('items', [])
                        if item.get('metadata', {}).get('labels', {}).get('app') == 'ckan'
                ][0]
                _log_container_error('CONTAINER LOGS', ckan_pod_name, 'ckan')
                kubectl.call(f'logs {ckan_pod_name}', namespace=instance_id)

            logs.info('Numbe of Failed Pods: %s' % len(failed_pods))
            for pod_meta in failed_pods:
                init_containers = pod_meta['status'].get('initContainerStatuses')
                pod_name = pod_meta['metadata']['name']
                if init_containers is not None:
                    logs.info('Checking Init Containers in %s' % pod_name)
                    for i, init_container in enumerate(init_containers):
                        if not init_container.get('ready'):
                            container_name = pod_meta['spec']['initContainers'][i]['name']
                            _log_container_error('INIT CONTAINER LOGS', pod_name, container_name)
                            kubectl.call(f'logs {pod_name} -c {container_name}', namespace=instance_id)
                        else:
                            logs.info('Init Containers are fine in %s' % pod_name)
                logs.info('Checking Containers in %s' % pod_name)
                container_stats = pod_meta['status'].get('containerStatuses')
                no_log_statuses = ['PodInitializing']
                pod_status = [
                    stat.get('state', {}).get('waiting', {}).get('reason') in no_log_statuses for stat in container_stats
                ]
                if all(pod_status):
                    logs.info('Pod %s looks good describing:' % pod_name)
                    _log_container_error('KUBECTL DESCRIBE POD', pod_name)
                    kubectl.call(f'describe pod {pod_name}', namespace=instance_id)
                else:
                    logs.info('Pod %s look did not start:' % pod_name)
                    for i, container in enumerate(container_stats):
                        container_name = pod_meta['spec']['containers'][i]['name']
                        _log_container_error('CONTAINER LOGS', pod_name, container_name)
                        kubectl.call(f'logs {pod_name}', namespace=instance_id)

            logs.info(100*'#')
            logs.info(100*'#')
            raise Exception('timed out waiting for instance events')


def _pre_update_hook_admin_user(instance, sub_domain, root_domain, instance_id, res, dry_run=False):
    ckan_admin_email = instance['spec'].get('ckanAdminEmail')
    if not ckan_admin_email:
        ckan_admin_email = f'admin@{sub_domain}.{root_domain}'
    ckan_admin_password = config_manager.get(key='CKAN_ADMIN_PASSWORD', secret_name='ckan-admin-password',
                                             namespace=instance_id, required=False)
    if ckan_admin_password:
        logs.info('using existing ckan admin user')
        res['ckan-admin-password'] = ckan_admin_password
    else:
        logs.info('Will create new ckan admin user', ckan_admin_email=ckan_admin_email)
        res['ckan-admin-email'] = ckan_admin_email
        res['ckan-admin-password'] = ckan_admin_password = binascii.hexlify(os.urandom(8)).decode()
        config_manager.set(key='CKAN_ADMIN_PASSWORD', value=ckan_admin_password, secret_name='ckan-admin-password',
                           namespace=instance_id,
                           dry_run=dry_run)


def _pre_update_hook_route(instance_id, skip_route, instance, res, dry_run=False):
    root_domain = routers_manager.get_default_root_domain()
    sub_domain = instance['spec'].get('sub-domain', f'ckan-cloud-{instance_id}')
    if not skip_route:
        # full domain to route to the instance
        instance_domain = instance['spec'].get('domain')
        if instance_domain and instance_domain != f'{sub_domain}.{root_domain}':
            logs.warning(f'instance domain was changed from {instance_domain} to {sub_domain}.{root_domain}')
            _pre_update_hook_modify_spec(instance_id, instance,
                                         lambda i: i.update(domain=f'{sub_domain}.{root_domain}'),
                                         dry_run=dry_run)
        # instance is added to router only if this is true, as all routers must use SSL and may use sans SSL too
        with_sans_ssl = instance['spec'].get('withSansSSL')
        if not with_sans_ssl:
            logs.warning(f'forcing with_sans_ssl, even though withSansSSL is disabled')
            _pre_update_hook_modify_spec(instance_id, instance,
                                         lambda i: i.update(withSansSSL=True),
                                         dry_run=dry_run)
        # subdomain to register on the default root domain
        register_subdomain = instance['spec'].get('registerSubdomain')
        if register_subdomain != sub_domain:
            logs.warning(f'instance register sub domain was changed from {register_subdomain} to {sub_domain}')
            _pre_update_hook_modify_spec(instance_id, instance,
                                         lambda i: i.update(registerSubdomain=sub_domain),
                                         dry_run=dry_run)
        res.update(**{'root-domain': root_domain, 'sub-domain': sub_domain})
        site_url = instance['spec'].get('siteUrl')
        if site_url != f'https://{sub_domain}.{root_domain}':
            logs.warning(f'instance siteUrl was changed from {site_url} to https://{sub_domain}.{root_domain}')
            _pre_update_hook_modify_spec(instance_id, instance,
                                         lambda i: i.update(siteUrl=f'https://{sub_domain}.{root_domain}'),
                                         dry_run=dry_run)
    return sub_domain, root_domain


def _pre_update_hook_override_spec(override_spec, instance):
    # applies override spec, but doesn't persist
    if override_spec:
        for k, v in override_spec.items():
            logs.info(f'Applying override spec {k}={v}')
            instance['spec'][k] = v


def _pre_update_hook_modify_spec(instance_id, instance, callback, dry_run=False):
    # applies changes to both the non-persistent spec and persists the changes on latest instance spec
    latest_instance = crds_manager.get(INSTANCE_CRD_SINGULAR, crds_manager.get_resource_name(
        INSTANCE_CRD_SINGULAR, instance_id
    ), required=True)
    callback(instance['spec'])
    callback(latest_instance['spec'])
    kubectl.apply(latest_instance, dry_run=dry_run)

def _scale_down_scale_up(deployment='ckan', namespace=None, replicas=1):
    logs.info('Scaling ckan replicas')
    kubectl.call(f'scale deployment {deployment} --replicas=0', namespace=namespace)
    kubectl.call(f'scale deployment {deployment} --replicas={replicas}', namespace=namespace)
    time.sleep(20)

def _log_container_error(text, pod_name, container_name=None):
    heading = f"****** {text} ******"
    logs.info()
    logs.info(heading)
    logs.info(f'Pod: {pod_name} - Container: {container_name}')
    logs.info("-" * len(heading))
    logs.info()
