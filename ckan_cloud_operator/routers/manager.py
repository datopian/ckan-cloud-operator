import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.routers.traefik import manager as traefik_manager


SUPPORTED_ROUTER_TYPES = ['traefik']


def _get_labels(router_name, router_type):
    return {'ckan-cloud/router-name': router_name, 'ckan-cloud/router-type': router_type}


def create(router_name, router_type):
    assert router_type in SUPPORTED_ROUTER_TYPES
    print(f'Creating CkanCloudRouter {router_name} (type={router_type})')
    labels = _get_labels(router_name, router_type)
    router = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRouter', router_name, labels)
    router['spec'] = {'type': router_type}
    kubectl.create(router)


def update(router_name, wait_ready=False):
    router = kubectl.get(f'CkanCloudRouter {router_name}')
    spec = router['spec']
    router_type = spec['type']
    assert router_type in SUPPORTED_ROUTER_TYPES
    print(f'Updating CkanCloudRouter {router_name} (type={router_type})')
    annotations = CkanRoutersAnnotations(router_name, router)
    labels = _get_labels(router_name, router_type)
    routes = kubectl.get_items_by_labels('CkanCloudRoute', labels, required=False)
    ckan_infra = CkanInfra()
    if router_type == 'traefik':
        router_manager_module = traefik_manager
    else:
        raise NotImplementedError(f'Unsupported router type: {router_type}')
    router_manager_module.update(router_name, wait_ready, ckan_infra, spec, annotations, routes)


def list(full=False, values_only=False, async_print=True):
    res = [] if async_print else None
    for router in kubectl.get('CkanCloudRouter')['items']:
        if values_only:
            data = {'name': router['metadata']['name'],
                    'type': router['spec']['type']}
        else:
            data = get(router)
            if not full:
                data = {'name': data['name'],
                        'type': data['type'],
                        'ready': data['ready']}
        if res is None:
            print(yaml.dump([data], default_flow_style=False))
        else:
            res.append(data)
    if res is not None:
        return res


def get(router_name_or_values):
    if type(router_name_or_values) == str:
        router_name = router_name_or_values
        router_values = kubectl.get(f'CkanCloudRouter {router_name}')
    else:
        router_name = router_name_or_values['metadata']['name']
        router_values = router_name_or_values
    spec = router_values['spec']
    router_type = spec['type']
    assert router_type in SUPPORTED_ROUTER_TYPES
    if router_type == 'traefik':
        router_manager_module = traefik_manager
    else:
        raise NotImplementedError(f'Unsupported router type: {router_type}')
    deployment_data = router_manager_module.get(router_name)
    routes = kubectl.get_items_by_labels('CkanCloudRoute', _get_labels(router_name, router_type), required=False)
    return {'name': router_name,
            'annotations': router_values['metadata']['annotations'],
            'routes': [route.get('spec') for route in routes.get('items', [])] if routes else [],
            'type': router_type,
            'deployment': deployment_data,
            'ready': deployment_data.get('ready', False)}


def install_crds():
    """Ensures installaion of the routers custom resource definitions on the cluster"""
    kubectl.install_crd('ckancloudrouters', 'ckancloudrouter', 'CkanCloudRouter')
    kubectl.install_crd('ckancloudroutes', 'ckancloudroute', 'CkanCloudRoute')
