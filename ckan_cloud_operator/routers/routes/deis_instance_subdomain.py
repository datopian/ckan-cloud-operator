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
    target_port = _get_instance_target_port(deis_instance_id)
    return f'http://{name}.{deis_instance_id}:{target_port}'


def pre_deployment_hook(route, labels):
    name, spec = _init_route(route)
    deis_instance_id = spec['deis-instance-id']
    if kubectl.get(f'ns {deis_instance_id}', required=False):
        target_port = _get_instance_target_port(deis_instance_id)
        print(f'updating route name {name} for deis instance {deis_instance_id} (port={target_port})')
        route_service = kubectl.get_resource('v1', 'Service', name, labels, namespace=deis_instance_id)
        route_service['spec'] = {
            'ports': [
                {'name': str(target_port), 'port': target_port}
            ],
            'selector': {
                'app': 'ckan'
            }
        }
        kubectl.apply(route_service)


def _get_instance_target_port(instance_id):
    target_port = 5000
    instance = kubectl.get(f'ckancloudckaninstance {instance_id}', required=False)
    if instance:
        _target_port = instance.get('spec', {}).get('routes', {}).get('target-port')
        if _target_port:
            target_port = _target_port
    return target_port
