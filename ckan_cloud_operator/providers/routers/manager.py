from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize(interactive=False):
    config_manager.interactive_set(
        {
            'env-id': None,
            'default-root-domain': None,
            'dns-provider': 'route53' if cluster_manager.get_provider_id() == 'aws' else None
        },
        configmap_name='routers-config',
        interactive=interactive
    )
    dns_provider = get_dns_provider()
    if dns_provider.lower() == 'none':
        if cluster_manager.get_provider_id() != 'minikube':
            return
    logs.info(dns_provider=dns_provider)
    if dns_provider == 'cloudflare':
        config_manager.interactive_set(
            {
                'cloudflare-email': None,
                'cloudflare-api-key': None
            },
            configmap_name='routers-config',
            interactive=interactive
        )
    routers_manager.install_crds()
    infra_router_name = routers_manager.get_default_infra_router_name()
    default_root_domain = config_manager.get('default-root-domain', configmap_name='routers-config', required=True)
    logs.info('Creating infra router', infra_router_name=infra_router_name, default_root_domain=default_root_domain)
    routers_manager.create(
        infra_router_name,
        routers_manager.get_traefik_router_spec(
            default_root_domain,
            config_manager.get('cloudflare-email', configmap_name='routers-config', required=False, default=None),
            config_manager.get('cloudflare-api-key', configmap_name='routers-config', required=False, default=None),
            dns_provider=dns_provider
        )
    )


def get_env_id():
    return config_get('env-id') or 'p'


def get_dns_provider():
    return config_manager.get(key='dns-provider', configmap_name='routers-config')


def get_default_root_domain():
    return config_get('default-root-domain')


def config_get(key):
    return config_manager.get(key, configmap_name='routers-config')


def get_cloudflare_credentials():
    return (
        config_manager.get('cloudflare-email', configmap_name='routers-config'),
        config_manager.get('cloudflare-api-key', configmap_name='routers-config')
    )


def update_dns_record(dns_provider, sub_domain, root_domain, load_balancer_ip_or_hostname, cloudflare_email=None,
                      cloudflare_auth_key=None):
    logs.info('updating DNS record', dns_provider=dns_provider, sub_domain=sub_domain, root_domain=root_domain,
              load_balancer_ip_or_hostname=load_balancer_ip_or_hostname,
              cloudflare_email=cloudflare_email,
              cloudflare_auth_key_len=len(cloudflare_auth_key) if cloudflare_auth_key else 0)
    if dns_provider == 'cloudflare':
        from ckan_cloud_operator import cloudflare
        cloudflare.update_a_record(cloudflare_email, cloudflare_auth_key, root_domain,
                                   f'{sub_domain}.{root_domain}', load_balancer_ip_or_hostname)
    elif dns_provider == 'route53':
        from ckan_cloud_operator.providers.cluster.aws import manager as aws_manager
        aws_manager.update_dns_record(sub_domain, root_domain, load_balancer_ip_or_hostname)
    elif dns_provider == 'azure':
        from ckan_cloud_operator.providers.cluster.azure import manager as azure_manager
        azure_manager.create_dns_record(sub_domain, root_domain, load_balancer_ip_or_hostname)
    elif dns_provider.lower() == 'none':
        return
    else:
        raise NotImplementedError()
