from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.infra import CkanInfra


def initialize(interactive=False):
    ckan_infra = CkanInfra(required=False)
    config_manager.interactive_set(
        {
            'http-endpoint': ckan_infra.SOLR_HTTP_ENDPOINT,
            'num-shards': ckan_infra.SOLR_NUM_SHARDS,
            'replication-factor': ckan_infra.SOLR_REPLICATION_FACTOR
        },
        secret_name='solr-config',
        interactive=interactive
    )


def get_http_endpoint():
    return config_get('http-endpoint')


def get_num_shards():
    return config_get('num-shards')


def get_replication_factor():
    return config_get('replication-factor')


def config_get(key):
    return config_manager.get(key, secret_name='solr-config')
