from ckan_cloud_operator import kubectl
from ckan_cloud_operator.infra import CkanInfra


from ckan_cloud_operator.routers.routes.backend_url_subdomain import (
    get_frontend_hostname,
    get_domain_parts,
    get_default_root_domain,
    get_route,
    _init_route
)


def get_backend_url(route):
    name, spec = _init_route(route)
    deis_instance_id = spec['deis-instance-id']
    return f'http://{name}.{deis_instance_id}:5000'


def pre_deployment_hook(route, labels):
    name, spec = _init_route(route)
    deis_instance_id = spec['deis-instance-id']
    if kubectl.get(f'ns {deis_instance_id}', required=False):
        print(f'updating route name {name} for deis instance {deis_instance_id}')
        route_service = kubectl.get_resource('v1', 'Service', name, labels, namespace=deis_instance_id)
        route_service['spec'] = {
            'ports': [
                {'name': '5000', 'port': 5000}
            ],
            'selector': {
                'app': 'ckan'
            }
        }
        kubectl.apply(route_service)
