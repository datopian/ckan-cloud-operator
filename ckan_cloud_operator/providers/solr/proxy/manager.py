import datetime

from urllib3.util import parse_url

from ckan_cloud_operator import kubectl

from .. import manager as solr_manager


def deploy():
    """Deploys a proxy inside the cluster which allows to access the centralized solr without authentication"""
    labels = {'app': 'ckan-cloud-solrcloud-proxy'}
    solr_url = parse_url(solr_manager.get_internal_http_endpoint())
    scheme = solr_url.scheme
    hostname = solr_url.hostname
    port = solr_url.port
    solr_user, solr_password = '', ''
    if solr_url.auth:
        solr_user, solr_password = solr_url.auth.split(':')
    if not port:
        port = '443' if scheme == 'https' else '8983'
    kubectl.update_secret('solrcloud-proxy', {
        'SOLR_URL': f'{scheme}://{hostname}:{port}',
        'SOLR_USER': solr_user,
        'SOLR_PASSWORD': solr_password
    })
    kubectl.apply(kubectl.get_deployment('solrcloud-proxy', labels, {
        'replicas': 1,
        'revisionHistoryLimit': 10,
        'strategy': {'type': 'RollingUpdate', },
        'template': {
            'metadata': {
                'labels': labels,
                'annotations': {
                    'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                }
            },
            'spec': {
                'containers': [
                    {
                        'name': 'solrcloud-proxy',
                        'image': 'viderum/ckan-cloud-operator-solrcloud-proxy',
                        'envFrom': [{'secretRef': {'name': 'solrcloud-proxy'}}],
                        'ports': [{'containerPort': 8983}],
                    }
                ]
            }
        }
    }))
    service = kubectl.get_resource('v1', 'Service', 'solrcloud-proxy', labels)
    service['spec'] = {
        'ports': [
            {'name': '8983', 'port': 8983}
        ],
        'selector': labels
    }
    kubectl.apply(service)

