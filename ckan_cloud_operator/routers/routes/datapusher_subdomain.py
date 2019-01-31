from ckan_cloud_operator import datapushers


from ckan_cloud_operator.routers.routes.backend_url_subdomain import (
    get_frontend_hostname,
    get_domain_parts,
    get_default_root_domain,
    get_route,
    _init_route
)


def get_backend_url(route):
    name, spec = _init_route(route)
    datapusher_name = spec['datapusher-name']
    return datapushers.get_service_url(datapusher_name)


def pre_deployment_hook(route, labels):
    name, spec = _init_route(route)
    datapusher_name = spec['datapusher-name']
    print(f'updating route name {name} for datapusher name {datapusher_name}')
    datapushers.update_service(datapusher_name, labels)
