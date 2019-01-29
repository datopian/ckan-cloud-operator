import toml
import time
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers.traefik import config as traefik_router_config
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import cloudflare


def _get_deployment_spec(router_name, labels, annotations):
    deployment_spec = {
        'replicas': 1,
        'revisionHistoryLimit': 5,
        'template': {
            'metadata': {
                'labels': labels
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
                    {'name': 'traefik-acme', 'persistentVolumeClaim': {'claimName': f'router-traefik-{router_name}'}}
                ]
            }
        }
    }
    if annotations.get_flag('letsencryptCloudflareEnabled'):
        container = deployment_spec['template']['spec']['containers'][0]
        container['ports'].append({'containerPort': 443})
        container['env'] = [
            {'name': 'CLOUDFLARE_EMAIL', 'value': annotations.get_secret('LETSENCRYPT_CLOUDFLARE_EMAIL')},
            annotations.get_pod_env_spec_from_secret('CLOUDFLARE_API_KEY', 'LETSENCRYPT_CLOUDFLARE_API_KEY')
        ]
    return deployment_spec


def _update(router_name, ckan_infra, spec, annotations, routes):
    resource_name = f'router-traefik-{router_name}'
    router_type = spec['type']
    storage_class_name = ckan_infra.MULTI_USER_STORAGE_CLASS_NAME
    labels = {
        'ckan-cloud/router-name': router_name,
        'ckan-cloud/router-type': router_type,
    }
    kubectl.apply(kubectl.get_configmap(resource_name, labels, {
        'traefik.toml': toml.dumps(traefik_router_config.get(annotations, routes))
    }))
    kubectl.apply(kubectl.get_persistent_volume_claim(resource_name, labels, {
        'storageClassName': storage_class_name,
        'accessModes': ['ReadWriteMany'],
        'resources': {
            'requests': {
                'storage': '1Mi'
            }
        }
    }))
    domains = {}
    for route in routes:
        root_domain, sub_domain = routes_manager.get_domain_parts(route)
        domains.setdefault(root_domain, []).append(sub_domain)
        routes_manager.pre_deployment_hook(route, labels)
    load_balancer = kubectl.get_resource('v1', 'Service', f'loadbalancer-{resource_name}', labels)
    load_balancer['spec'] = {
        'ports': [
            {'name': '80', 'port': 80},
            {'name': '443', 'port': 443},
        ],
        'selector': labels,
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
    cloudflare_auth_key = annotations.get_secret('LETSENCRYPT_CLOUDFLARE_API_KEY')
    cloudflare_auth_email = annotations.get_secret('LETSENCRYPT_CLOUDFLARE_EMAIL')
    for root_domain, sub_domains in domains.items():
        for sub_domain in sub_domains:
            cloudflare.update_a_record(cloudflare_auth_email, cloudflare_auth_key, root_domain,
                                       f'{sub_domain}.{root_domain}', load_balancer_ip)
    kubectl.apply(kubectl.get_deployment(resource_name, labels,
                                         _get_deployment_spec(router_name, labels, annotations)))


def update(router_name, wait_ready, ckan_infra, spec, annotations, routes):
    old_deployment = kubectl.get(f'deployment router-traefik-{router_name}', required=False)
    old_generation = old_deployment.get('metadata', {}).get('generation') if old_deployment else None
    if old_generation:
        expected_new_generation = old_generation + 1
    else:
        expected_new_generation = 1
    print(f'old deployment generation: {old_generation}')
    annotations.update_status(
        'router', 'created',
        lambda: _update(router_name, ckan_infra, spec, annotations, routes),
        force_update=True
    )
    while True:
        time.sleep(.2)
        new_deployment = kubectl.get(f'deployment router-traefik-{router_name}', required=False)
        if not new_deployment: continue
        new_generation = new_deployment.get('metadata', {}).get('generation')
        if not new_generation: continue
        if new_generation == old_generation: continue
        if new_generation != expected_new_generation:
            raise Exception(f'Invalid generation: {new_generation} (expected: {expected_new_generation}')
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
