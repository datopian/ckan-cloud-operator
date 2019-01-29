from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.routers.traefik import deployment as traefik_deployment


def _init_router(router_name):
    router = kubectl.get(f'CkanCloudRouter {router_name}')
    assert router['spec']['type'] == 'traefik'
    annotations = CkanRoutersAnnotations(router_name, router)
    ckan_infra = CkanInfra()
    return router, annotations, ckan_infra


def enable_letsencrypt_cloudflare(router_name, cloudflare_email, cloudflare_api_key):
    print('Enabling SSL using lets encrypt and cloudflare')
    router, annotations, ckan_infra = _init_router(router_name)
    annotations.update_flag('letsencryptCloudflareEnabled', lambda: annotations.set_secrets({
        'LETSENCRYPT_CLOUDFLARE_EMAIL': cloudflare_email,
        'LETSENCRYPT_CLOUDFLARE_API_KEY': cloudflare_api_key
    }), force_update=True)


def set_default_root_domain(router_name, root_domain):
    print(f'Setting default root domain for router {router_name} to {root_domain}')
    router, annotations, ckan_infra = _init_router(router_name)
    annotations.json_annotate('default-root-domain', root_domain)


def set_deis_instance_subdomain_route(router_name, deis_instance, root_domain, sub_domain, route_name):
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
    assert ckan_infra.ROUTERS_ENV_ID
    sub_domain = f'cc-{ckan_infra.ROUTERS_ENV_ID}-{deis_instance.id}'
    root_domain = annotations.get_json_annotation('default-root-domain')
    route_name = f'deis-instance-{deis_instance.id}-default'
    return set_deis_instance_subdomain_route(router_name, deis_instance, root_domain, sub_domain, route_name)


def set_datapusher_subdomain_route(router_name, datapusher_name, root_domain, sub_domain, route_name):
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
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} CkanCloudRoute') == 0,
        kubectl.call(f'delete --ignore-not-found CkanCloudRouter {router_name}') == 0,
    ]):
        print('Removing finalizers')
        success = True
        for route in kubectl.get(f'CkanCloudRoute -l ckan-cloud/router-name={router_name}')['items']:
            route_name = route['metadata']['name']
            if kubectl.call(
                    f'patch CkanCloudRoute {route_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
            ) != 0:
                success = False
        if kubectl.call(
                f'patch CkanCloudRouter {router_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
        ) != 0:
            success = False
        assert success
    else:
        raise Exception('Deletion failed')


def get(router_name):
    return traefik_deployment.get(router_name)


def update(router_name, wait_ready, ckan_infra, spec, annotations, routes):
    return traefik_deployment.update(router_name, wait_ready, ckan_infra, spec, annotations, routes)
