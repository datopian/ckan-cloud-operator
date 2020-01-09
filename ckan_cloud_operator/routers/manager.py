import yaml
import hashlib

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.routers.traefik import manager as traefik_manager
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator.providers.routers.manager import get_env_id, get_default_root_domain, get_dns_provider


ROUTER_TYPES = {
    'traefik': {
        'default': True,
        'manager': traefik_manager
    }
}

DEFAULT_ROUTER_TYPE = [k for k,v in ROUTER_TYPES.items() if v.get('default')][0]


def create(router_name, router_spec):
    from ckan_cloud_operator.providers.cluster.manager import get_or_create_multi_user_volume_claim
    from ckan_cloud_operator.routers.traefik.deployment import get_label_suffixes

    router_type = router_spec.get('type')
    default_root_domain = router_spec.get('default-root-domain')
    assert router_type in ROUTER_TYPES and default_root_domain, f'Invalid router spec: {router_spec}'
    get(router_name, only_dns=True, failfast=True)
    print(f'Creating CkanCloudRouter {router_name} {router_spec}')
    labels = _get_labels(router_name, router_type)
    router = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRouter', router_name, labels,
                                  spec=dict(router_spec, **{'type': router_type}))
    router_manager = ROUTER_TYPES[router_type]['manager']
    router = router_manager.create(router)
    get_or_create_multi_user_volume_claim(get_label_suffixes(router_name, router_type))
    annotations = CkanRoutersAnnotations(router_name, router)
    annotations.json_annotate('default-root-domain', default_root_domain)


def get_traefik_router_spec(default_root_domain=None, cloudflare_email=None, cloudflare_api_key=None,
                            wildcard_ssl_domain=None, external_domains=False, dns_provider=None):
    if not default_root_domain: default_root_domain = 'default'
    if not cloudflare_email: cloudflare_email = 'default'
    if not cloudflare_api_key: cloudflare_api_key = 'default'
    return {
        'type': 'traefik',
        'default-root-domain': default_root_domain,
        # the cloudflare spec is not saved as part of the CkanCloudRouter spec
        # it is removed and saved as a secret by the traefik router manager
        'cloudflare': {
            'email': cloudflare_email,
            'api-key': cloudflare_api_key
        },
        'wildcard-ssl-domain': wildcard_ssl_domain,
        'external-domains': bool(external_domains),
        'dns-provider': dns_provider
    }


def update(router_name, wait_ready=False, dry_run=False):
    router, spec, router_type, annotations, labels, router_type_config = _init_router(router_name)
    print(f'Updating CkanCloudRouter {router_name} (type={router_type}) (labels={labels})')
    routes = routes_manager.list(labels)
    router_type_config['manager'].update(router_name, wait_ready, spec, annotations, routes, dry_run=dry_run)


def list(full=False, values_only=False, async_print=True):
    res = None if async_print else []
    for router in kubectl.get('CkanCloudRouter')['items']:
        if values_only:
            data = {'name': router['metadata']['name'],
                    'type': router['spec']['type']}
        else:
            data = get(router)
            if not full:
                data = {'name': data['name'],
                        'type': data['type'],
                        'ready': data['ready']}
        if res is None:
            print(yaml.dump([data], default_flow_style=False))
        else:
            res.append(data)
    if res is not None:
        return res


def get(router_name_or_values, required=False, only_dns=False, failfast=False):
    if type(router_name_or_values) == str:
        router_name = router_name_or_values
        router_values = kubectl.get(f'CkanCloudRouter {router_name}', required=required)
    else:
        router_name = router_name_or_values['metadata']['name']
        router_values = router_name_or_values
    router, spec, router_type, annotations, labels, router_type_config = _init_router(router_name, router_values, required=required)
    if router:
        dns_data = router_type_config['manager'].get(router_name, 'dns', router, failfast=True)
        if not only_dns:
            deployment_data = router_type_config['manager'].get(router_name, 'deployment')
            routes = routes_manager.list(_get_labels(router_name, router_type))
        else:
            deployment_data = None
            routes = None
        if only_dns:
            return {'name': router_name,
                    'dns': dns_data}
        else:
            return {'name': router_name,
                    'annotations': router_values['metadata']['annotations'],
                    'routes': [route.get('spec') for route in routes] if routes else [],
                    'type': router_type,
                    'deployment': deployment_data,
                    'ready': deployment_data.get('ready', False),
                    'dns': dns_data,
                    'spec': {'ready': True, **router_values['spec']}}
    else:
        return None


def create_subdomain_route(router_name, route_spec, dry_run=False):
    target_type = route_spec['target-type']
    sub_domain = route_spec.get('sub-domain')
    root_domain = route_spec.get('root-domain')
    if target_type == 'datapusher':
        target_resource_id = route_spec['datapusher-name']
    elif target_type == 'deis-instance':
        target_resource_id = route_spec['deis-instance-id']
    elif target_type == 'backend-url':
        target_resource_id = route_spec['target-resource-id']
    elif target_type == 'ckan-instance':
        target_resource_id = route_spec['ckan-instance-id']
    elif target_type == 'app-instance':
        target_resource_id = route_spec['app-instance-id']
    else:
        raise Exception(f'Invalid route spec: {route_spec}')
    sub_domain, root_domain = _get_default_sub_root_domain(sub_domain, root_domain, target_resource_id)
    route_name = 'cc' + hashlib.sha3_224(f'{target_type} {target_resource_id} {root_domain} {sub_domain}'.encode()).hexdigest()

    logs.info(f'initializing router {router_name}')
    router, spec, router_type, annotations, labels, router_type_config = _init_router(router_name)
    route_type = f'{target_type}-subdomain'
    labels = labels or {}
    labels.update(**{
        'ckan-cloud/route-type': route_type,
        'ckan-cloud/route-root-domain': root_domain,
        'ckan-cloud/route-sub-domain': sub_domain,
        'ckan-cloud/route-target-type': target_type,
        'ckan-cloud/route-target-resource-id': target_resource_id,
    })
    spec = {
        'name': route_name,
        'type': route_type,
        'root-domain': root_domain,
        'sub-domain': sub_domain,
        'router_name': router_name,
        'router_type': router_type,
        'route-target-type': target_type,
        'route-target-resource-id': target_resource_id,
    }
    if target_type == 'datapusher':
        labels['ckan-cloud/route-datapusher-name'] = spec['datapusher-name'] = route_spec['datapusher-name']
    elif target_type == 'deis-instance':
        labels['ckan-cloud/route-deis-instance-id'] = spec['deis-instance-id'] = route_spec['deis-instance-id']
    elif target_type == 'backend-url':
        spec['backend-url'] = route_spec['backend-url']
    elif target_type == 'ckan-instance':
        labels['ckan-cloud/route-ckan-instance-id'] = spec['ckan-instance-id'] = route_spec['ckan-instance-id']
    elif target_type == 'app-instance':
        labels['ckan-cloud/route-app-instance-id'] = spec['app-instance-id'] = route_spec['app-instance-id']
    route = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRoute', route_name, labels, spec=spec)
    kubectl.apply(route, dry_run=dry_run)


def install_crds():
    """Ensures installaion of the custom resource definitions on the cluster"""
    kubectl.install_crd('ckancloudrouters', 'ckancloudrouter', 'CkanCloudRouter')
    routes_manager.install_crds()


def delete(router_name, router_type=None):
    if router_type:
        router_type_config = ROUTER_TYPES[router_type]
    else:
        router, spec, router_type, annotations, labels, router_type_config = _init_router(router_name)
    router_type_config['manager'].delete(router_name)


def get_datapusher_routes(datapusher_name, edit=False):
    labels = {'ckan-cloud/route-datapusher-name': datapusher_name}
    if edit: kubectl.edit_items_by_labels('CkanCloudRoute', labels)
    else: return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


def get_backend_url_routes(target_resorce_id, edit=False):
    labels = {'ckan-cloud/route-target-resource-id': target_resorce_id}
    if edit: kubectl.edit_items_by_labels('CkanCloudRoute', labels)
    else: return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


def get_deis_instance_routes(deis_instance_id, edit=False):
    labels = {'ckan-cloud/route-deis-instance-id': deis_instance_id}
    if edit: kubectl.edit_items_by_labels('CkanCloudRoute', labels)
    else: return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


def get_ckan_instance_routes(ckan_instance_id, edit=False):
    labels = {'ckan-cloud/route-ckan-instance-id': ckan_instance_id}
    if edit: kubectl.edit_items_by_labels('CkanCloudRoute', labels)
    else: return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


def get_app_instance_routes(app_instance_id, edit=False):
    labels = {'ckan-cloud/route-app-instance-id': app_instance_id}
    if edit: kubectl.edit_items_by_labels('CkanCloudRoute', labels)
    else: return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


def get_all_routes():
    return kubectl.get('CkanCloudRoute')['items']


def get_domain_routes(root_domain=None, sub_domain=None):
    if not root_domain or root_domain == get_default_root_domain():
        root_domain = 'default'
    assert sub_domain or root_domain != 'default', 'cannot delete all routes from default root domain'
    labels = {'ckan-cloud/route-root-domain': root_domain}
    if sub_domain:
        labels['ckan-cloud/route-sub-domain']: sub_domain
    return kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)


# delete_routes mtehod is dangerous - better to delete manually via kubectl
#
# def delete_routes(routes=None, deis_instance_id=None, backend_url_target_resource_id=None, datapusher_name=None,
#                   root_domain=None, sub_domain=None):
#     if deis_instance_id:
#         assert not routes and not backend_url_target_resource_id and not datapusher_name and not root_domain and not sub_domain
#         routes = get_deis_instance_routes(deis_instance_id)
#     elif backend_url_target_resource_id:
#         assert not routes and not datapusher_name and not root_domain and not sub_domain
#         routes = get_backend_url_routes(backend_url_target_resource_id)
#     elif datapusher_name:
#         assert not routes and not root_domain and not sub_domain
#         routes = get_datapusher_routes(datapusher_name)
#     elif root_domain or sub_domain:
#         assert not routes
#         routes = get_domain_routes(root_domain, sub_domain)
#     assert routes
#     delete_route_names = set()
#     update_router_names = set()
#     for route in routes:
#         delete_route_names.add(route['metadata']['name'])
#         update_router_names.add(route['spec']['router_name'])
#     if len(delete_route_names) > 0:
#         delete_route_names = ' '.join(delete_route_names)
#         kubectl.check_call(f'delete CkanCloudRoute {delete_route_names}')
#         for router_name in update_router_names:
#             update(router_name)


def get_default_infra_router_name():
    return 'infra-1'


def get_route_frontend_hostname(route):
    frontend_hostname = routes_manager.get_frontend_hostname(route)
    if frontend_hostname.endswith('.default'):
        return frontend_hostname.replace('.default', '.' + get_default_root_domain())
    else:
        return frontend_hostname


def get_cloudflare_rate_limits(root_domain):
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    from ckan_cloud_operator import cloudflare
    return cloudflare.get_zone_rate_limits(*routers_manager.get_cloudflare_credentials(), root_domain)


def _get_labels(router_name, router_type):
    return {'ckan-cloud/router-name': router_name, 'ckan-cloud/router-type': router_type}


def _init_router(router_name, router_values=None, required=False):
    router = kubectl.get(f'CkanCloudRouter {router_name}', required=required) if not router_values else router_values
    if router:
        spec = router['spec']
        router_type = spec['type']
        assert router_type in ROUTER_TYPES, f'Unsupported router type: {router_type}'
        router_type_config = ROUTER_TYPES[router_type]
        annotations = CkanRoutersAnnotations(router_name, router)
        labels = _get_labels(router_name, router_type)
        logs.debug_verbose('_init_router', router=router, router_type_config=router_type_config, labels=labels)
        return router, spec, router_type, annotations, labels, router_type_config
    else:
        logs.debug_verbose('_init_router', router=router, router_type_config=None, labels=None)
        return None, None, None, None, None, None


def _get_default_sub_root_domain(sub_domain, root_domain, default_sub_domain_suffix):
    if not root_domain or root_domain == 'default':
        root_domain = 'default'
    if not sub_domain or sub_domain == 'default':
        env_id = get_env_id()
        assert env_id, 'missing env id value'
        sub_domain = f'cc-{env_id}-{default_sub_domain_suffix}'
    _validate_sub_root_domain(sub_domain, root_domain)
    return sub_domain, root_domain


def _validate_sub_root_domain(sub_domain, root_domain):
    env_id = get_env_id()
    assert env_id, 'missing env id value'
    assert env_id == 'p' or root_domain == 'default', 'non-default root domain is not allowed for non production environmnets'
    assert env_id == 'p' or sub_domain.startswith(f'cc-{env_id}-'), 'non-default sub-domains are not allowed for non production environments'
