import subprocess
import yaml
import datetime
import toml
import time
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import cloudflare


def create(name, router_type):
    assert router_type in ['traefik']
    labels =  {'ckan-cloud/router-type': router_type}
    router = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRouter', name, labels)
    router['spec'] = {'type': router_type}
    kubectl.create(router)


def _get_traefik_toml(annotations, routes, router_name):
    data = {
        'debug': False,
        'defaultEntryPoints': ['http'],
        'entryPoints': {
            'http': {
                'address': ':80'
            }
        },
        'ping': {
            'entryPoint': 'http'
        },
        'accessLog': {},
        'file': {},
        'frontends': {},
        'backends': {},
    }
    if annotations.get_flag('letsencryptCloudflareEnabled'):
        data['defaultEntryPoints'].append('https')
        data['entryPoints']['https'] = {
            'address': ':443',
            'tls': {}
        }
        data['acme'] = {
            'email': annotations.get_secret('LETSENCRYPT_CLOUDFLARE_EMAIL'),
            'storage': '/traefik-acme/acme.json',
            'entryPoint': 'https',
            'dnsChallenge': {
                'provider': 'cloudflare'
            }
        }
    domains = {}
    for route in routes:
        route_spec = route['spec']
        route_type = route_spec['type']
        if route_type == 'deis-instance-subdomain':
            route_name = route['metadata']['name']
            root_domain = route_spec['root-domain']
            sub_domain = route_spec['sub-domain']
            domains.setdefault(root_domain, []).append(sub_domain)
            deis_instance_id = route_spec['deis-instance-id']
            data['backends'][route_name] = {
                'servers': {
                    'server1': {
                        'url': f'http://{route_name}.{deis_instance_id}:5000'
                    }
                }
            }
            data['frontends'][route_name] = {
                'backend': route_name,
                'passHostHeader': True,
                'headers': {
                    'SSLRedirect': bool(annotations.get_flag('letsencryptCloudflareEnabled'))
                },
                'routes': {
                    'route1': {
                        'rule': f'Host:{sub_domain}.{root_domain}'
                    }
                }
            }
        else:
            raise NotImplementedError(f'route type {route_type} is not supported yet')
    if annotations.get_flag('letsencryptCloudflareEnabled'):
        data['acme']['domains'] = [{
            'main': root_domain,
            'sans': [f'{sub_domain}.{root_domain}' for sub_domain in sub_domains]
        } for root_domain, sub_domains in domains.items()]
    return data


def _get_traefik_deployment_spec(name, labels, annotations):
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
                            {'name': 'traefik-acme', 'mountPath': '/traefik-acme', 'subPath': f'router-traefik-{name}'}
                        ],
                        'args': ['--configFile=/etc-traefik/traefik.toml']
                    }
                ],
                'volumes': [
                    {'name': 'etc-traefik', 'configMap': {'name': f'router-traefik-{name}'}},
                    {'name': 'traefik-acme', 'persistentVolumeClaim': {'claimName': f'router-traefik-{name}'}}
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


def _update_traefik_deployment(name, ckan_infra, spec, annotations, routes):
    resource_name = f'router-traefik-{name}'
    router_type = spec['type']
    storage_class_name = ckan_infra.MULTI_USER_STORAGE_CLASS_NAME
    labels = {
        'ckan-cloud/router-name': name,
        'ckan-cloud/router-type': router_type,
    }

    kubectl.apply(kubectl.get_configmap(resource_name, labels, {
        'traefik.toml': toml.dumps(_get_traefik_toml(annotations, routes, name))
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
        route_spec = route['spec']
        route_type = route_spec['type']
        if route_type == 'deis-instance-subdomain':
            route_name = route['metadata']['name']
            root_domain = route_spec['root-domain']
            sub_domain = route_spec['sub-domain']
            domains.setdefault(root_domain, []).append(sub_domain)
            deis_instance_id = route_spec['deis-instance-id']
            print(f'updating route name {route_name} for deis instance {deis_instance_id}')
            route_service = kubectl.get_resource('v1', 'Service', route_name, labels, namespace=deis_instance_id)
            route_service['spec'] = {
                'ports': [
                    {'name': '5000', 'port': 5000}
                ],
                'selector': {
                    'app': 'ckan'
                }
            }
            kubectl.apply(route_service)
        else:
            raise NotImplementedError(f'route type {route_type} is not supported yet')
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
                                         _get_traefik_deployment_spec(name, labels, annotations)))


def update(name, wait_ready=False):
    print(f'updating CkanCloudRouter {name}')
    router = kubectl.get(f'CkanCloudRouter {name}')
    spec = router['spec']
    router_type = spec['type']
    assert router_type in ['traefik']
    annotations = CkanRoutersAnnotations(name, router)
    routes = kubectl.get(f'CkanCloudRoute -l ckan-cloud/router-name={name}', required=False)
    routes = routes['items'] if routes else []
    ckan_infra = CkanInfra()
    if router_type == 'traefik':
        old_deployment = kubectl.get(f'deployment router-traefik-{name}', required=False)
        old_generation = old_deployment.get('metadata', {}).get('generation') if old_deployment else None
        if old_generation:
            expected_new_generation = old_generation + 1
        else:
            expected_new_generation = 1
        print(f'old deployment generation: {old_generation}')
        annotations.update_status(
            'router', 'created',
            lambda: _update_traefik_deployment(name, ckan_infra, spec, annotations, routes),
            force_update=True
        )
        while True:
            time.sleep(.2)
            new_deployment = kubectl.get(f'deployment router-traefik-{name}', required=False)
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
                if get(name)['ready']: break
                print('.')
    else:
        raise NotImplementedError(f'Unsupported router type: {router_type}')


def list(full=False, values_only=False):
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
        print(yaml.dump([data], default_flow_style=False))


def get(name_or_values):
    if type(name_or_values) == str:
        name = name_or_values
        values = kubectl.get(f'CkanCloudRouter {name}')
    else:
        name = name_or_values['metadata']['name']
        values = name_or_values
    spec = values['spec']
    router_type = spec['type']
    if spec['type'] == 'traefik':
        deployment_data = traefik_deployment_get(name)
        routes = kubectl.get(f'CkanCloudRoute -l ckan-cloud/router-name={name}', required=False)
        return {'name': name,
                'annotations': values['metadata']['annotations'],
                'routes': [route.get('spec') for route in routes.get('items',[])] if routes else [],
                'type': router_type,
                'deployment': deployment_data,
                'ready': deployment_data.get('ready', False)}
    else:
        raise NotImplementedError(f'Invalid router type: {router_type}')


def traefik_deployment_get(name):
    deployment = kubectl.get(f'deployment/router-traefik-{name}', required=False)
    if deployment:
        return kubectl.get_deployment_detailed_status(deployment, f'ckan-cloud/router-name={name}', 'traefik')
    else:
        return {'ready': False}


def install_crds():
    """Ensures installaion of the routers custom resource definitions on the cluster"""
    kubectl.install_crd('ckancloudrouters', 'ckancloudrouter', 'CkanCloudRouter')
    kubectl.install_crd('ckancloudroutes', 'ckancloudroute', 'CkanCloudRoute')


def _init_traefik_router(name):
    router = kubectl.get(f'CkanCloudRouter {name}')
    assert router['spec']['type'] == 'traefik'
    annotations = CkanRoutersAnnotations(name, router)
    ckan_infra = CkanInfra()
    return router, annotations, ckan_infra


def traefik(command, router_name, args):
    if command == 'enable-letsencrypt-cloudflare':
        print('Enabling SSL using lets encrypt and cloudflare')
        router, annotations, ckan_infra = _init_traefik_router(router_name)
        cloudflare_email, cloudflare_api_key = args
        annotations.update_flag('letsencryptCloudflareEnabled', lambda: annotations.set_secrets({
            'LETSENCRYPT_CLOUDFLARE_EMAIL': cloudflare_email,
            'LETSENCRYPT_CLOUDFLARE_API_KEY': cloudflare_api_key
        }), force_update=True)
    elif command == 'set-deis-instance-subdomain-route':
        deis_instance, root_domain, sub_domain, route_name = args
        print(f'Setting deis instance route from {sub_domain}.{root_domain} to deis ckan instance id {deis_instance.id}')
        labels = {'ckan-cloud/router-type': 'traefik',
                  'ckan-cloud/router-name': router_name,
                  'ckan-cloud/route-type': 'deis-instance-subdomain'}
        route = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudRoute', route_name, labels)
        route['spec'] = {'type': 'deis-instance-subdomain',
                         'root-domain': root_domain,
                         'sub-domain': sub_domain,
                         'deis-instance-id': deis_instance.id}
        kubectl.apply(route)
    else:
        raise NotImplementedError(f'Invalid traefik command: {command} {args}')


class CkanRoutersAnnotations(kubectl.BaseAnnotations):
    """Manage router annotations"""

    @property
    def FLAGS(self):
        """Boolean flags which are saved as annotations on the resource"""
        return [
            'forceCreateAnnotations',
            'letsencryptCloudflareEnabled'
        ]

    @property
    def STATUSES(self):
        """Predefined statuses which are saved as annotations on the resource"""
        return {
            'router': ['created']
        }

    @property
    def SECRET_ANNOTATIONS(self):
        """Sensitive details which are saved in a secret related to the resource"""
        return [
            'LETSENCRYPT_CLOUDFLARE_EMAIL',
            'LETSENCRYPT_CLOUDFLARE_API_KEY'
        ]

    @property
    def RESOURCE_KIND(self):
        return 'CkanCloudRouter'
