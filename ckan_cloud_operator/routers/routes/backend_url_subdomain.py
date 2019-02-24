def get_backend_url(route):
    name, spec = _init_route(route)
    return spec['backend-url']


def get_frontend_hostname(route):
    _, spec = _init_route(route)
    root_domain = spec['root-domain']
    sub_domain = spec['sub-domain']
    return f'{sub_domain}.{root_domain}'


def pre_deployment_hook(route, labels):
    pass


def get_domain_parts(route):
    _, spec = _init_route(route)
    return spec['root-domain'], spec['sub-domain']


def get_default_root_domain():
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    default_root_domain = routers_manager.get_default_root_domain()
    assert default_root_domain, 'missing ckan-infra ROUTERS_DEFAULT_ROOT_DOMAIN'
    return default_root_domain


def get_route(route):
    _init_route(route)
    root_domain = route['spec'].get('root-domain')
    if not root_domain or root_domain == 'default':
        route['spec']['root-domain'] = get_default_root_domain()
    return route


def _init_route(route):
    spec = route['spec']
    name = route['metadata']['name']
    return name, spec
