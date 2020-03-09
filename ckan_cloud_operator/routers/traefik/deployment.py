import toml
import time
import hashlib
import json

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.routers.traefik import config as traefik_router_config
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import cloudflare
from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.config import manager as config_manager


def _get_deployment_spec(router_name, router_type, annotations, image=None, httpauth_secrets=None, dns_provider=None):
    volume_spec = cluster_manager.get_or_create_multi_user_volume_claim(get_label_suffixes(router_name, router_type))
    httpauth_secrets_volume_mounts, httpauth_secrets_volumes = [], []
    if httpauth_secrets:
        added_secrets = []
        for httpauth_secret in httpauth_secrets:
            if httpauth_secret in added_secrets: continue
            added_secrets.append(httpauth_secret)
            httpauth_secrets_volumes.append({
                'name': httpauth_secret, 'secret': {'secretName': httpauth_secret}
            })
            httpauth_secrets_volume_mounts.append({
                'name': httpauth_secret, 'mountPath': f'/httpauth-{httpauth_secret}'
            })
    container_spec_overrides = config_manager.get(
        'container-spec-overrides',
        configmap_name=f'traefik-router-{router_name}-deployment',
        required=False,
        default=None
    )
    deployment_spec = {
        'replicas': 1,
        'revisionHistoryLimit': 5,
        'selector': {
            'matchLabels': get_labels(router_name, router_type, for_deployment=True)
        },
        'template': {
            'metadata': {
                'labels': get_labels(router_name, router_type, for_deployment=True)
            },
            'spec': {
                'containers': [
                    {
                        'name': 'traefik',
                        'image': image or 'traefik:1.6-alpine',
                        'ports': [{'containerPort': 80}],
                        'volumeMounts': [
                            {'name': 'etc-traefik', 'mountPath': '/etc-traefik'},
                            {'name': 'traefik-acme', 'mountPath': '/traefik-acme', 'subPath': f'router-traefik-{router_name}'},
                            *httpauth_secrets_volume_mounts,
                        ],
                        'args': ['--configFile=/etc-traefik/traefik.toml'],
                        **(json.loads(container_spec_overrides) if container_spec_overrides else {})
                    }
                ],
                'volumes': [
                    {'name': 'etc-traefik', 'configMap': {'name': f'router-traefik-{router_name}'}},
                    dict(volume_spec, name='traefik-acme'),
                    *httpauth_secrets_volumes,
                ]
            }
        }
    }
    if dns_provider == 'route53':
        logs.info('Traefik deployment: adding SSL support using AWS Route53')
        container = deployment_spec['template']['spec']['containers'][0]
        container['ports'].append({'containerPort': 443})
        aws_credentials = cluster_manager.get_provider().get_aws_credentials()
        secret_name = f'ckancloudrouter-{router_name}-route53'
        kubectl.update_secret(secret_name, {
            'AWS_ACCESS_KEY_ID': aws_credentials['access'],
            'AWS_SECRET_ACCESS_KEY': aws_credentials['secret'],
            'AWS_REGION': aws_credentials['region']
        }, labels=get_labels(router_name, router_type))
        container['envFrom'] = [{'secretRef': {'name': secret_name}}]
    elif annotations.get_flag('letsencryptCloudflareEnabled'):
        logs.info('Traefik deployment: adding SSL support using Cloudflare')
        container = deployment_spec['template']['spec']['containers'][0]
        container['ports'].append({'containerPort': 443})
        cloudflare_email, cloudflare_api_key = get_cloudflare_credentials()
        secret_name = f'ckancloudrouter-{router_name}-cloudflare'
        kubectl.update_secret(secret_name, {
            'CLOUDFLARE_EMAIL': cloudflare_email,
            'CLOUDFLARE_API_KEY': cloudflare_api_key,
        }, labels=get_labels(router_name, router_type))
        container['envFrom'] = [{'secretRef': {'name': secret_name}}]
    elif dns_provider == 'azure':
        logs.info('Traefik deployment: adding SSL support using Azure DNS')
        container = deployment_spec['template']['spec']['containers'][0]
        container['ports'].append({'containerPort': 443})
        azure_credendials = cluster_manager.get_provider().get_azure_credentials()
        secret_name = f'ckancloudrouter-{router_name}-azure'
        kubectl.update_secret(secret_name, {
            'AZURE_CLIENT_ID': azure_credendials['azure-client-id'],
            'AZURE_CLIENT_SECRET':  azure_credendials['azure-client-secret'],
            'AZURE_SUBSCRIPTION_ID': azure_credendials['azure-subscribtion-id'],
            'AZURE_TENANT_ID': azure_credendials['azure-tenant-id'],
            'AZURE_RESOURCE_GROUP': azure_credendials['azure-resource-group']
        }, labels=get_labels(router_name, router_type))
        container['envFrom'] = [{'secretRef': {'name': secret_name}}]
    else:
        logs.info('Not configuring SSL support for Traefik deployment')
    return deployment_spec


def _get_resource_name(router_name):
    return f'router-traefik-{router_name}'


def _update(router_name, spec, annotations, routes):
    dns_provider = spec.get('dns-provider', 'cloudflare')
    if dns_provider == 'none':
        logs.info('No DNS provider, not setting up ingress')
        return
    resource_name = _get_resource_name(router_name)
    router_type = spec['type']
    cloudflare_email, cloudflare_auth_key = get_cloudflare_credentials()
    external_domains = spec.get('external-domains')
    logs.info('updating traefik deployment', resource_name=resource_name, router_type=router_type,
              cloudflare_email=cloudflare_email, cloudflare_auth_key_len=len(cloudflare_auth_key) if cloudflare_auth_key else 0,
              external_domains=external_domains, dns_provider=dns_provider)
    kubectl.apply(kubectl.get_configmap(
        resource_name, get_labels(router_name, router_type),
        {'traefik.toml': toml.dumps(traefik_router_config.get(
            routes, cloudflare_email,
            enable_access_log=bool(spec.get('enable-access-log')),
            wildcard_ssl_domain=spec.get('wildcard-ssl-domain'),
            external_domains=external_domains,
            dns_provider=dns_provider,
            force=True
        ))}
    ))
    domains = {}
    httpauth_secrets = []
    for route in routes:
        root_domain, sub_domain = routes_manager.get_domain_parts(route)
        domains.setdefault(root_domain, []).append(sub_domain)
        routes_manager.pre_deployment_hook(route, get_labels(router_name, router_type))
        if route['spec'].get('httpauth-secret') and route['spec']['httpauth-secret'] not in httpauth_secrets:
            httpauth_secrets.append(route['spec']['httpauth-secret'])
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
    load_balancer_ip = get_load_balancer_ip(router_name)
    logs.info(f'load balancer ip: {load_balancer_ip}')
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    if external_domains:
        from ckan_cloud_operator.providers.routers import manager as routers_manager
        external_domains_router_root_domain = routers_manager.get_default_root_domain()
        env_id = routers_manager.get_env_id()
        assert router_name.startswith('prod-'), f'invalid external domains router name: {router_name}'
        external_domains_router_sub_domain = f'cc-{env_id}-{router_name}'
        routers_manager.update_dns_record(
            dns_provider, external_domains_router_sub_domain, external_domains_router_root_domain,
            load_balancer_ip, cloudflare_email, cloudflare_auth_key
        )
    else:
        for root_domain, sub_domains in domains.items():
            for sub_domain in sub_domains:
                routers_manager.update_dns_record(
                    dns_provider, sub_domain, root_domain,
                    load_balancer_ip, cloudflare_email, cloudflare_auth_key
                )
    kubectl.apply(kubectl.get_deployment(
        resource_name, get_labels(router_name, router_type, for_deployment=True),
        _get_deployment_spec(
            router_name, router_type, annotations,
            image=('traefik:1.7' if (external_domains or len(httpauth_secrets) > 0) else None),
            httpauth_secrets=httpauth_secrets,
            dns_provider=dns_provider
        )
    ))


def get_load_balancer_ip(router_name, failfast=False):
    resource_name = _get_resource_name(router_name)
    RETRIES = 10
    for retries in range(RETRIES):
        load_balancer = kubectl.get(f'service loadbalancer-{resource_name}', required=False)

        if load_balancer:
            ingresses = load_balancer.get('status', {}).get('loadBalancer', {}).get('ingress', [])
            if len(ingresses) > 0:
                assert len(ingresses) == 1
                if cluster_manager.get_provider_id() == 'aws':
                    load_balancer_hostname = ingresses[0].get('hostname')
                    if load_balancer_hostname:
                        return load_balancer_hostname
                    logs.warning('Failed to get hostname, retrying %r' % ingresses[0])
                else:
                    load_balancer_ip = ingresses[0].get('ip')
                    if load_balancer_ip:
                        return load_balancer_ip
                    logs.warning('Failed to get ip, retrying %r' % ingresses[0])
        if failfast:
            return None
        else:
            time.sleep(60)
        assert retries < RETRIES - 1, "Gave up on waiting for load balancer IP"


def get_cloudflare_credentials():
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    cloudflare_email, cloudflare_auth_key = routers_manager.get_cloudflare_credentials()
    return cloudflare_email, cloudflare_auth_key


def update(router_name, wait_ready, spec, annotations, routes, dry_run=False):
    old_deployment = kubectl.get(f'deployment router-traefik-{router_name}', required=False)
    old_generation = old_deployment.get('metadata', {}).get('generation') if old_deployment else None
    expected_new_generation = old_generation + 3 if old_generation else None
    if expected_new_generation:
        print(f'old deployment generation: {old_generation}')
    else:
        print('Creating new deployment')
    if not dry_run:
        annotations.update_status(
            'router', 'created',
            lambda: _update(router_name, spec, annotations, routes),
            force_update=True
        )
        if expected_new_generation:
            _scale_down_scale_up(f'router-traefik-{router_name}')
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


def get_dns_data(router_name, router, failfast=False):
    external_domains = router['spec'].get('external-domains')
    data = {
        'load-balancer-ip': get_load_balancer_ip(router_name, failfast=failfast),
    }
    if external_domains:
        from ckan_cloud_operator.providers.routers import manager as routers_manager
        external_domains_router_root_domain = routers_manager.get_default_root_domain()
        env_id = routers_manager.get_env_id()
        assert router_name.startswith('prod-'), f'invalid external domains router name: {router_name}'
        external_domains_router_sub_domain = f'cc-{env_id}-{router_name}'
        data['external-domain'] = f'{external_domains_router_sub_domain}.{external_domains_router_root_domain}'
    return data


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

def _scale_down_scale_up(deployment='router-traefik-instances-default', replicas=1):
    kubectl.call(f'scale deployment {deployment} --replicas=0')
    kubectl.call(f'scale deployment {deployment} --replicas={replicas}')
