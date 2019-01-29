from ckan_cloud_operator.routers.routes import deis_instance_subdomain


def get_module(route):
    route_type = route['spec']['type']
    if route_type == 'deis-instance-subdomain':
        module = deis_instance_subdomain
    else:
        raise Exception(f'Invalid route type: {route_type}')
    return module


def get_name(route):
    return route['metadata']['name']


def get_backend_url(route):
    return get_module(route).get_backend_url(route)


def get_frontend_host(route):
    return get_module(route).get_frontend_host(route)


def pre_deployment_hook(route, labels):
    return get_module(route).pre_deployment_hook(route, labels)


def get_domain_parts(route):
    root_domain, sub_domain = get_module(route).get_domain_parts(route)
    return root_domain, sub_domain
