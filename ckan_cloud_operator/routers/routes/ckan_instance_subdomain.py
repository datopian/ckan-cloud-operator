from ckan_cloud_operator import kubectl

from ckan_cloud_operator.providers.ckan.instance import manager as ckan_instance_manager


from ckan_cloud_operator.routers.routes.backend_url_subdomain import (
    get_frontend_hostname,
    get_domain_parts,
    get_default_root_domain,
    get_route,
    _init_route,
    pre_deployment_hook
)


def get_backend_url(route):
    name, spec = _init_route(route)
    return ckan_instance_manager.get_backend_url(spec['ckan-instance-id'])
