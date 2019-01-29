from ckan_cloud_operator import kubectl


def _init_route(route):
    spec = route['spec']
    assert spec['type'] == 'deis-instance-subdomain'
    name = route['metadata']['name']
    return name, spec


def get_backend_url(route):
    name, spec = _init_route(route)
    deis_instance_id = spec['deis-instance-id']
    return f'http://{name}.{deis_instance_id}:5000'


def get_frontend_host(route):
    _, spec = _init_route(route)
    root_domain = spec['root-domain']
    sub_domain = spec['sub-domain']
    return f'Host:{sub_domain}.{root_domain}'


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


def get_domain_parts(route):
    _, spec = _init_route(route)
    return spec['root-domain'], spec['sub-domain']
