#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None, short=False): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix, short=short)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)

################################
# custom provider code starts here
#


import tempfile
import traceback
import json
import datetime
import subprocess
import time
from ruamel import yaml
from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.drivers.kubectl import rbac as kubectl_rbac_driver
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.apps.constants import APP_CRD_SINGULAR
from ckan_cloud_operator.drivers.helm import driver as helm_driver


def create(tiller_namespace_name=None, chart_repo=None, chart_version=None, chart_release_name=None,
           values=None, values_filename=None, with_service_account=False, chart_name=None,
           chart_repo_name=None, app_type=None, values_json=None,
           **create_kwargs):
    if values_filename:
        assert not values and not values_json
        with open(values_filename) as f:
            values = yaml.safe_load(f.read())
    elif values:
        assert not values_filename and not values_json
    elif values_json:
        assert not values_filename and not values
        values = json.loads(values_json)
    values = values or {}
    spec = {
        **({'tiller-namespace-name': tiller_namespace_name} if tiller_namespace_name else {}),
        **({'chart-name': chart_name} if chart_name else {}),
        **({'chart-repo': chart_repo} if chart_repo else {}),
        **({'chart-repo-name': chart_repo_name} if chart_repo_name else {}),
        **({'chart-version': chart_version} if chart_version else {}),
        **({'chart-release-name': chart_release_name} if chart_release_name else {}),
        **({'with-service-account': True} if with_service_account else {}),
        **({'app-type': app_type} if app_type else {}),
        **values,
    }
    assert 'values' not in create_kwargs
    from ckan_cloud_operator.providers.apps import manager as apps_manager
    return apps_manager.create('helm', values=spec, **create_kwargs)


def update(instance_id, instance, dry_run=False):
    tiller_namespace_name = _get_tiller_namespace_name(instance_id, instance)
    logs.debug('Updating helm-based instance deployment',
               instance_id=instance_id, tiller_namespace_name=tiller_namespace_name)
    chart_repo_name = instance['spec'].get("chart-repo-name")
    assert chart_repo_name, 'missing spec attribute: chart-repo-name'
    logs.info(chart_repo_name=chart_repo_name)
    chart_repo = instance['spec'].get("chart-repo")
    assert chart_repo or chart_repo_name in ['stable'], 'missing spec attribute: chart-repo'
    logs.info(chart_repo=chart_repo)
    chart_name = instance['spec'].get('chart-name')
    assert chart_name, 'missing spec attribute: chart-name'
    logs.info(chart_name=chart_name)
    chart_version = instance['spec'].get("chart-version", "")
    logs.info(chart_version=chart_version)
    release_name = _get_helm_release_name(instance_id, instance)
    logs.info(release_name=release_name,)
    _pre_update_hook_modify_spec(instance_id, instance, lambda i: i.update(**{
        'release-name': release_name,
        'chart-version': chart_version,
        'chart-name': chart_name,
        'chart-repo': chart_repo,
        'chart-repo-name': chart_repo_name,
    }))
    deploy_kwargs = dict(
        values=instance['spec'].get('values', {}),
        tiller_namespace_name=tiller_namespace_name,
        chart_repo=chart_repo,
        chart_version=chart_version,
        chart_name=chart_name,
        release_name=release_name,
        instance_id=instance_id,
        dry_run=dry_run,
        chart_repo_name=chart_repo_name
    )
    app_type = instance['spec'].get('app-type')
    if app_type:
        _get_app_type_manager(app_type).pre_deploy_hook(instance_id, instance, deploy_kwargs)
    _helm_deploy(**deploy_kwargs)
    if app_type:
        _get_app_type_manager(app_type).post_deploy_hook(instance_id, instance, deploy_kwargs)


def get(instance_id, instance=None):
    res = {
        'ready': None,
        'helm_metadata': {
            'ckan_instance_id': instance_id,
            'namespace': instance_id,
            'status_generated_at': datetime.datetime.now(),
            'status_generated_from': subprocess.check_output(["hostname"]).decode().strip(),
        }
    }
    app_type = instance['spec'].get('app-type')
    if app_type:
        _get_app_type_manager(app_type).get(instance_id, instance, res)
    return res


def delete(instance_id, instance):
    tiller_namespace_name = _get_tiller_namespace_name(instance_id, instance)
    release_name = _get_helm_release_name(instance_id, instance)
    logs.info(tiller_namespace_name=tiller_namespace_name, release_name=release_name)
    errors = []
    try:
        logs.info(f'Deleting helm release {release_name}')
        delete_kwargs=dict(tiller_namespace=tiller_namespace_name, release_name=release_name)
        app_type = instance['spec'].get('app-type')
        if app_type:
            _get_app_type_manager(app_type).pre_delete_hook(instance_id, instance, delete_kwargs)
        helm_driver.delete(**delete_kwargs)
        if app_type:
            _get_app_type_manager(app_type).post_delete_hook(instance_id, instance, delete_kwargs)
    except Exception as e:
        logs.warning(traceback.format_exc())
        errors.append(f'Failed to delete helm release')
    if kubectl.call(f'delete --wait=false namespace {instance_id}') != 0:
        errors.append(f'Failed to delete namespace')
    assert len(errors) == 0, ', '.join(errors)


def get_backend_url(instance_id, instance):
    app_type = instance['spec'].get('app-type')
    if app_type:
        backend_url = instance['spec'].get('backend-url')
        if backend_url:
            try:
                backend_url = backend_url.format(instance_id=instance_id)
            except Exception:
                backend_url = None
        return _get_app_type_manager(app_type).get_backend_url(instance_id, instance, backend_url)
    else:
        return instance['spec'].get('backend-url').format(
            instance_id=instance_id
        )


def pre_update_hook(instance_id, instance, override_spec, skip_route=False, dry_run=False):
    _init_namespace(instance_id, instance, dry_run=dry_run)
    _pre_update_hook_override_spec(override_spec, instance)
    res = {}
    sub_domain, root_domain = _pre_update_hook_route(instance_id, skip_route, instance, res, dry_run=dry_run)
    app_type = instance['spec'].get('app-type')
    logs.info(app_type=app_type)
    if app_type:
        logs.info(f'Running {app_type} app pre_update_hook')
        _get_app_type_manager(app_type).pre_update_hook(
            instance_id, instance, res, sub_domain, root_domain,
            lambda callback: _pre_update_hook_modify_spec(instance_id, instance, callback, dry_run=dry_run)
        )
    return res


def _init_namespace(instance_id, instance, dry_run=False):
    logs.debug('Initializing helm-based instance deployment namespace', namespace=instance_id)
    if kubectl.get('ns', instance_id, required=False):
        logs.info(f'instance namespace already exists ({instance_id})')
    else:
        logs.info(f'creating instance namespace ({instance_id})')
        kubectl.apply(kubectl.get_resource('v1', 'Namespace', instance_id, {}), dry_run=dry_run)
        if instance['spec'].get('with-service-account'):
            service_account_name = instance['spec'].get('service-account-name', f'ckan-{instance_id}-operator')
            logs.info('Creating service account', service_account_name=service_account_name)
            if not dry_run:
                kubectl_rbac_driver.update_service_account(service_account_name, {}, namespace=instance_id)
            role_name = f'{service_account_name}-role'
            logs.debug('Creating role and binding to the service account', role_name=role_name)
            if not dry_run:
                rbac_rules = instance['spec'].get('service-account-rules', [
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
                ])
                kubectl_rbac_driver.update_role(role_name, {}, rbac_rules, namespace=instance_id)
                kubectl_rbac_driver.update_role_binding(
                    name=f'{service_account_name}-rolebinding',
                    role_name=f'{service_account_name}-role',
                    namespace=instance_id,
                    service_account_name=service_account_name,
                    labels={}
                )


def _pre_update_hook_route(instance_id, skip_route, instance, res, dry_run=False):
    root_domain = routers_manager.get_default_root_domain()
    sub_domain = instance['spec'].get('sub-domain', f'ckan-cloud-app-{instance_id}')
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
            if k != 'values':
                instance['spec'][k] = v
            else:
                instance['spec'].setdefault('values', {}).update(v)


def _pre_update_hook_modify_spec(instance_id, instance, callback, dry_run=False):
    # applies changes to both the non-persistent spec and persists the changes on latest instance spec
    latest_instance = crds_manager.get(APP_CRD_SINGULAR, name=instance_id, required=True)
    callback(instance['spec'])
    callback(latest_instance['spec'])
    kubectl.apply(latest_instance, dry_run=dry_run)


def _helm_deploy(values, tiller_namespace_name, chart_repo, chart_name, chart_version, release_name, instance_id,
                 dry_run=False, chart_repo_name=None):
    assert chart_repo_name, 'chart-repo-name is required'
    helm_driver.init(tiller_namespace_name)
    time.sleep(10) # wait for tiller pod to be ready
    logs.info(f'Deploying helm chart {chart_repo_name} {chart_repo} {chart_version} {chart_name} to release {release_name} '
              f'(instance_id={instance_id})')
    with tempfile.NamedTemporaryFile('w') as f:
        yaml.dump(values, f, default_flow_style=False)
        f.flush()
        helm_driver.deploy(tiller_namespace=tiller_namespace_name,
                           chart_repo=chart_repo,
                           chart_name=chart_name,
                           chart_version=chart_version,
                           release_name=release_name,
                           values_filename=f.name,
                           namespace=instance_id,
                           dry_run=dry_run,
                           chart_repo_name=chart_repo_name)


def _get_tiller_namespace_name(instance_id, instance):
    return instance['spec'].get('tiller-namespace-name', _get_resource_name('tiller'))


def _get_helm_release_name(instance_id, instance):
    return instance['spec'].get('chart-release-name', _get_resource_name(instance_id, short=False))


def _get_app_type_manager(app_type):
    if app_type == 'provisioning':
        from . import type_provisioning as app_type_manager
    elif app_type == 'jenkins':
        from . import type_jenkins as app_type_manager
    elif app_type == 'elk':
        from . import type_elk as app_type_manager
    else:
        raise NotImplementedError(f'Unknown app type: {app_type}')
    return app_type_manager
