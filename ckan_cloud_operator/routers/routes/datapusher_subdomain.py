from ckan_cloud_operator import datapushers


def _init_route(route):
    spec = route['spec']
    assert spec['type'] == 'datapusher-subdomain'
    name = route['metadata']['name']
    return name, spec


def get_backend_url(route):
    name, spec = _init_route(route)
    datapusher_name = spec['datapusher-name']
    return datapushers.get_service_url(datapusher_name)


def get_frontend_host(route):
    _, spec = _init_route(route)
    root_domain = spec['root-domain']
    sub_domain = spec['sub-domain']
    return f'Host:{sub_domain}.{root_domain}'


def pre_deployment_hook(route, labels):
    name, spec = _init_route(route)
    datapusher_name = spec['datapusher-name']
    print(f'updating route name {name} for datapusher name {datapusher_name}')
    datapushers.update_service(datapusher_name, labels)


def get_domain_parts(route):
    _, spec = _init_route(route)
    return spec['root-domain'], spec['sub-domain']
