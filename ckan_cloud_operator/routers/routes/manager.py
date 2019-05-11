from ckan_cloud_operator.routers.routes import deis_instance_subdomain
from ckan_cloud_operator.routers.routes import ckan_instance_subdomain
from ckan_cloud_operator.routers.routes import app_instance_subdomain
from ckan_cloud_operator.routers.routes import datapusher_subdomain
from ckan_cloud_operator.routers.routes import backend_url_subdomain
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs


def get_module(route):
    route_type = route['spec']['type']
    if route_type == 'deis-instance-subdomain':
        module = deis_instance_subdomain
    elif route_type == 'ckan-instance-subdomain':
        module = ckan_instance_subdomain
    elif route_type == 'app-instance-subdomain':
        module = app_instance_subdomain
    elif route_type == 'datapusher-subdomain':
        module = datapusher_subdomain
    elif route_type == 'backend-url-subdomain':
        module = backend_url_subdomain
    else:
        raise Exception(f'Invalid route type: {route_type}')
    return module


def list(router_labels):
    routes = kubectl.get_items_by_labels('CkanCloudRoute', router_labels, required=False)
    logs.debug_verbose(router_labels=router_labels, routes=routes)
    _routes = []
    if routes:
        for route in routes:
            route = get_module(route).get_route(route)
            logs.debug_verbose(route=route)
            _routes.append(route)
    return _routes


def get_name(route):
    return route['metadata']['name']


def get_backend_url(route):
    return get_module(route).get_backend_url(route)


def get_frontend_hostname(route):
    return get_module(route).get_frontend_hostname(route)


def pre_deployment_hook(route, labels):
    return get_module(route).pre_deployment_hook(route, labels)


def get_domain_parts(route):
    root_domain, sub_domain = get_module(route).get_domain_parts(route)
    return root_domain, sub_domain


def install_crds():
    kubectl.install_crd('ckancloudroutes', 'ckancloudroute', 'CkanCloudRoute')
