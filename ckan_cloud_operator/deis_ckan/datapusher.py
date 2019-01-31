from urllib.parse import urlparse

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.infra import CkanInfra



def get_datapusher_url(instance_datapusher_url):
    if instance_datapusher_url and len(instance_datapusher_url) > 10:
        hostname = urlparse(instance_datapusher_url).hostname
        if hostname.endswith('.l3.ckan.io'):
            datapusher_name = hostname.replace('.l3.ckan.io', '')
        elif hostname.endswith('.ckan.io'):
            datapusher_name = hostname.replace('.ckan.io', '')
        else:
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
                        default_root_domain = CkanInfra().ROUTERS_DEFAULT_ROOT_DOMAIN
                        assert default_root_domain, 'missing ckan-infra ROUTERS_DEFAULT_ROOT_DOMAIN'
                        root_domain = default_root_domain
                    return 'https://{}.{}/'.format(sub_domain, root_domain)
    return None
