import toml
import time

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers.traefik import config as traefik_router_config
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import cloudflare
from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.labels import manager as labels_manager


def _get_deployment_spec(router_name, router_type, annotations):
    volume_spec = cluster_manager.get_or_create_multi_user_volume_claim(get_label_suffixes(router_name, router_type))
    deployment_spec = {
        'replicas': 1,
        'revisionHistoryLimit': 5,
        'template': {
            'metadata': {
                'labels': get_labels(router_name, router_type, for_deployment=True)
            },
            'spec': {
                'containers': [
                    {
                        'name': 'traefik',
                        'image': 'traefik:1.6-alpine',
                        'ports': [{'containerPort': 80}],
                        'volumeMounts': [
                            {'name': 'etc-traefik', 'mountPath': '/etc-traefik'},
                            {'name': 'traefik-acme', 'mountPath': '/traefik-acme', 'subPath': f'router-traefik-{router_name}'}
                        ],
                        'args': ['--configFile=/etc-traefik/traefik.toml']
                    }
                ],
                'volumes': [
                    {'name': 'etc-traefik', 'configMap': {'name': f'router-traefik-{router_name}'}},
                    dict(volume_spec, name='traefik-acme')
                ]
            }
        }
    }
    if annotations.get_flag('letsencryptCloudflareEnabled'):
        container = deployment_spec['template']['spec']['containers'][0]
        container['ports'].append({'containerPort': 443})
        cloudflare_email, cloudflare_api_key = get_cloudflare_credentials()
        secret_name = f'ckancloudrouter-{router_name}-cloudflare'
        kubectl.update_secret(secret_name, {
            'CLOUDFLARE_EMAIL': cloudflare_email,
            'CLOUDFLARE_API_KEY': cloudflare_api_key,
        }, labels=get_labels(router_name, router_type))
        container['envFrom'] = [{'secretRef': {'name': secret_name}}]
    return deployment_spec


def _update(router_name, spec, annotations, routes):
    resource_name = f'router-traefik-{router_name}'
    router_type = spec['type']
    cloudflare_email, cloudflare_auth_key = get_cloudflare_credentials()
    kubectl.apply(kubectl.get_configmap(
        resource_name, get_labels(router_name, router_type),
        {'traefik.toml': toml.dumps(traefik_router_config.get(routes, cloudflare_email))}
    ))
    domains = {}
    for route in routes:
        root_domain, sub_domain = routes_manager.get_domain_parts(route)
        domains.setdefault(root_domain, []).append(sub_domain)
        routes_manager.pre_deployment_hook(route, get_labels(router_name, router_type))
    load_balancer = kubectl.get_resource(
        'v1', 'Service', f'loadbalancer-{resource_name}',
        get_labels(router_name, router_type)
    )
    load_balancer['spec'] = {
        'ports': [
            {'name': '80', 'port': 80},
            {'name': '443', 'port': 443},
        ],
        'selector': {
            'app': get_labels(router_name, router_type, for_deployment=True)['app']
        },
        'type': 'LoadBalancer'
    }
    kubectl.apply(load_balancer)
    while True:
        time.sleep(.2)
        load_balancer = kubectl.get(f'service loadbalancer-{resource_name}', required=False)
        if not load_balancer: continue
        ingresses = load_balancer.get('status', {}).get('loadBalancer', {}).get('ingress', [])
        if len(ingresses) == 0: continue
        assert len(ingresses) == 1
        load_balancer_ip = ingresses[0].get('ip')
        if load_balancer_ip:
            break
    print(f'load balancer ip: {load_balancer_ip}')
    for root_domain, sub_domains in domains.items():
        for sub_domain in sub_domains:
            cloudflare.update_a_record(cloudflare_email, cloudflare_auth_key, root_domain,
                                       f'{sub_domain}.{root_domain}', load_balancer_ip)
    kubectl.apply(kubectl.get_deployment(
        resource_name, get_labels(router_name, router_type, for_deployment=True),
        _get_deployment_spec(router_name, router_type, annotations)
    ))


def get_cloudflare_credentials():
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    cloudflare_email, cloudflare_auth_key = routers_manager.get_cloudflare_credentials()
    return cloudflare_email, cloudflare_auth_key


def update(router_name, wait_ready, spec, annotations, routes):
    old_deployment = kubectl.get(f'deployment router-traefik-{router_name}', required=False)
    old_generation = old_deployment.get('metadata', {}).get('generation') if old_deployment else None
    expected_new_generation = old_generation + 1 if old_generation else None
    if expected_new_generation:
        print(f'old deployment generation: {old_generation}')
    else:
        print('Creating new deployment')
    annotations.update_status(
        'router', 'created',
        lambda: _update(router_name, spec, annotations, routes),
        force_update=True
    )
    if expected_new_generation:
        while True:
            time.sleep(.2)
            new_deployment = kubectl.get(f'deployment router-traefik-{router_name}', required=False)
            if not new_deployment: continue
            new_generation = new_deployment.get('metadata', {}).get('generation')
            if not new_generation: continue
            if new_generation == old_generation: continue
            if new_generation != expected_new_generation:
                raise Exception(f'Invalid generation: {new_generation} (expected: {expected_new_generation})')
            print(f'new deployment generation: {new_generation}')
            break
    if wait_ready:
        print('Waiting for instance to be ready...')
        while time.sleep(2):
            if get(router_name)['ready']: break
            print('.')


def get(router_name):
    deployment = kubectl.get(f'deployment/router-traefik-{router_name}', required=False)
    if deployment:
        return kubectl.get_deployment_detailed_status(
            deployment, f'ckan-cloud/router-name={router_name}', 'traefik'
        )
    else:
        return {'ready': False}


def get_label_suffixes(router_name, router_type):
    return {
        'router-name': router_name,
        'router-type': router_type
    }


def get_labels(router_name, router_type, for_deployment=False):
    label_prefix = labels_manager.get_label_prefix()
    extra_labels = {'app': f'{label_prefix}-router-{router_name}'} if for_deployment else {}
    return labels_manager.get_resource_labels(
        get_label_suffixes(router_name, router_type),
        extra_labels=extra_labels
    )
