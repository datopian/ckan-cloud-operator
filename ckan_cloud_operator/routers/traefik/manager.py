from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.routers.traefik import deployment as traefik_deployment


def create(router):
    router_name = router['metadata']['name']
    router_spec = router['spec']
    cloudflare_spec = router_spec.get('cloudflare', {})
    cloudflare_email = cloudflare_spec.get('email')
    cloudflare_api_key = cloudflare_spec.get('api-key')
    default_root_domain = router_spec.get('default-root-domain')
    assert all([cloudflare_email, cloudflare_api_key, default_root_domain]), f'invalid traefik router spec: {router_spec}'
    # cloudflare credentials are stored in a secret, not in the spec
    del router_spec['cloudflare']
    kubectl.create(router)
    annotations = CkanRoutersAnnotations(router_name, router)
    annotations.update_flag('letsencryptCloudflareEnabled', lambda: annotations.set_secrets({
        'LETSENCRYPT_CLOUDFLARE_EMAIL': cloudflare_email,
        'LETSENCRYPT_CLOUDFLARE_API_KEY': cloudflare_api_key
    }), force_update=True)
    return router

def get_default_root_domain(router_name):
    router, annotations, ckan_infra = _init_router(router_name)
    return annotations.get_json_annotation('default-root-domain')


def set_initialized(router_name):
    print(f'Setting router {router_name} as initialized and ready to accept routes')
    router, annotations, ckan_infra = _init_router(router_name)
    annotations.set_status('router', 'initialized')


def is_initialized(router_name=None, annotations=None):
    if not annotations:
        _, annotations, _ = _init_router(router_name)
    return annotations.get_status('router', 'initialized')


def set_deis_instance_subdomain_route(router_name, deis_instance, root_domain, sub_domain, route_name):
    assert is_initialized(router_name), f'router {router_name} is not initialized'
    print(f'Setting deis instance route from {sub_domain}.{root_domain} to deis ckan instance id {deis_instance.id}')
    labels = {'ckan-cloud/router-type': 'traefik',
              'ckan-cloud/router-name': router_name,
              'ckan-cloud/route-type': 'deis-instance-subdomain'}
    route = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRoute', route_name, labels)
    route['spec'] = {'type': 'deis-instance-subdomain',
                     'root-domain': root_domain,
                     'sub-domain': sub_domain,
                     'deis-instance-id': deis_instance.id}
    kubectl.apply(route)


def set_instance_default_subdomain_route(router_name, deis_instance):
    router, annotations, ckan_infra = _init_router(router_name)
    assert is_initialized(annotations=annotations), f'router {router_name} is not initialized'
    assert ckan_infra.ROUTERS_ENV_ID, 'missing ckan infra ROUTERS_ENV_ID value'
    sub_domain = f'cc-{ckan_infra.ROUTERS_ENV_ID}-{deis_instance.id}'
    root_domain = annotations.get_json_annotation('default-root-domain')
    route_name = f'deis-instance-{deis_instance.id}-default'
    return set_deis_instance_subdomain_route(router_name, deis_instance, root_domain, sub_domain, route_name)


def set_datapusher_subdomain_route(router_name, datapusher_name, root_domain, sub_domain, route_name):
    assert is_initialized(router_name), f'router {router_name} is not initialized'
    print(f'Setting datapusher route from {sub_domain}.{root_domain} to datapusher name {datapusher_name}')
    labels = {'ckan-cloud/router-type': 'traefik',
              'ckan-cloud/router-name': router_name,
              'ckan-cloud/route-type': 'datapusher-subdomain',
              'ckan-cloud/datapusher-name': datapusher_name}
    route = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRoute', route_name, labels)
    route['spec'] = {'type': 'datapusher-subdomain',
                     'root-domain': root_domain,
                     'sub-domain': sub_domain,
                     'datapusher-name': datapusher_name}
    kubectl.apply(route)


def delete(router_name):
    print(f'Deleting traefik router {router_name}')
    if all([
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} deployment') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} service') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} secret') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} configmap') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} PersistentVolumeClaim') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} CkanCloudRoute') == 0,
        kubectl.call(f'delete --ignore-not-found CkanCloudRouter {router_name}') == 0,
    ]):
        print('Removing finalizers')
        success = True
        routes = kubectl.get_items_by_labels('CkanCloudRoute', {'ckan-cloud/router-name': router_name}, required=False)
        if not routes: routes = []
        for route in routes:
            route_name = route['metadata']['name']
            if kubectl.call(
                    f'patch CkanCloudRoute {route_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
            ) != 0:
                success = False
        if kubectl.get(f'CkanCloudRouter {router_name}', required=False):
            if kubectl.call(
                    f'patch CkanCloudRouter {router_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
            ) != 0:
                success = False
        assert success
    else:
        raise Exception('Deletion failed')


def get(router_name, attr='deployment'):
    deployment_data = traefik_deployment.get(router_name)
    return deployment_data if attr == 'deployment' else {'deployment': deployment_data}


def update(router_name, wait_ready, spec, annotations, routes):
    return traefik_deployment.update(router_name, wait_ready, spec, annotations, routes)


def _init_router(router_name):
    router = kubectl.get(f'CkanCloudRouter {router_name}')
    assert router['spec']['type'] == 'traefik'
    annotations = CkanRoutersAnnotations(router_name, router)
    ckan_infra = CkanInfra()
    return router, annotations, ckan_infra
