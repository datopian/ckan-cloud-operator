from urllib.parse import urlparse

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.routers import manager as routers_manager


def get_datapusher_url(instance_datapusher_url):
    if instance_datapusher_url and len(instance_datapusher_url) > 10:
        hostname = urlparse(instance_datapusher_url).hostname
        if hostname.endswith('.l3.ckan.io'):
            datapusher_name = hostname.replace('.l3.ckan.io', '')
        elif hostname.endswith('.ckan.io'):
            datapusher_name = hostname.replace('.ckan.io', '')
        else:
            logs.warning(f'failed to parse datapusher url from instance datapusher url: {instance_datapusher_url}')
            datapusher_name = None
        if datapusher_name:
            routes = kubectl.get(
                f'CkanCloudRoute -l ckan-cloud/route-datapusher-name={datapusher_name},ckan-cloud/route-type=datapusher-subdomain',
                required=False
            )
            if routes:
                routes = routes.get('items', [])
                if len(routes) > 0:
                    assert len(routes) == 1
                    route = routes[0]
                    sub_domain = route['spec']['sub-domain']
                    root_domain = route['spec']['root-domain']
                    assert sub_domain and sub_domain != 'default', f'invalid sub_domain: {sub_domain}'
                    if not root_domain or root_domain == 'default':
                        default_root_domain = routers_manager.get_default_root_domain()
                        assert default_root_domain, 'missing routers default root domain'
                        root_domain = default_root_domain
                    return 'https://{}.{}/'.format(sub_domain, root_domain)
                else:
                    logs.warning(f'failed to find route for datapusher: {datapusher_name}')
            else:
                logs.warning(f'failed to find route for datapusher: {datapusher_name}')
    return None
