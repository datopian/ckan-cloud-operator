from ckan_cloud_operator import kubectl
from urllib.parse import urlparse


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
                f'CkanCloudRoute -l ckan-cloud/datapusher-name={datapusher_name},ckan-cloud/route-type=datapusher-subdomain',
                required=False
            )
            if routes:
                routes = routes.get('items', [])
                if len(routes) > 0:
                    assert len(routes) == 1
                    route = routes[0]
                    return 'https://{}.{}/'.format(
                        route['spec']['sub-domain'],
                        route['spec']['root-domain'],
                    )
    return None
