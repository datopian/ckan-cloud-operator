from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.routers import manager as routers_manager


def initialize(interactive=False):
    ckan_infra = CkanInfra(required=False)
    config_manager.interactive_set(
        {
            'env-id': ckan_infra.ROUTERS_ENV_ID,
            'default-root-domain': ckan_infra.ROUTERS_DEFAULT_ROOT_DOMAIN,
            'cloudflare-email': ckan_infra.ROUTERS_DEFAULT_CLOUDFLARE_EMAIL,
            'cloudflare-api-key': ckan_infra.ROUTERS_DEFAULT_CLOUDFLARE_AUTH_KEY
        },
        configmap_name='routers-config',
        interactive=interactive
    )
    routers_manager.install_crds()
    routers_manager.create(
        routers_manager.get_default_infra_router_name(),
        routers_manager.get_traefik_router_spec(
            config_manager.get('default-root-domain', configmap_name='routers-config'),
            config_manager.get('cloudflare-email', configmap_name='routers-config'),
            config_manager.get('cloudflare-api-key', configmap_name='routers-config')
        )
    )


def get_env_id():
    return config_get('env-id')


def get_default_root_domain():
    return config_get('default-root-domain')


def config_get(key):
    return config_manager.get(key, configmap_name='routers-config')


def get_cloudflare_credentials():
    return (
        config_manager.get('cloudflare-email', configmap_name='routers-config'),
        config_manager.get('cloudflare-api-key', configmap_name='routers-config')
    )
