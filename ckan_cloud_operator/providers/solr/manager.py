import subprocess
import json

from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator import logs

from .constants import PROVIDER_SUBMODULE
from .solrcloud.constants import PROVIDER_ID as solrcloud_provider_id


def initialize(interactive=False):
    ckan_infra = CkanInfra(required=False)
    solr_config = config_manager.interactive_set(
        {
            'self-hosted': True
        },
        secret_name='solr-config',
        interactive=interactive
    )
    if is_self_hosted(solr_config):
        initialize_self_hosted(interactive=interactive)
    else:
        config_manager.interactive_set(
            {
                'http-endpoint': ckan_infra.SOLR_HTTP_ENDPOINT,
            },
            secret_name='solr-config',
            interactive=interactive
        )
    config_manager.interactive_set(
        {
            'num-shards': ckan_infra.SOLR_NUM_SHARDS or '1',
            'replication-factor': ckan_infra.SOLR_REPLICATION_FACTOR or '3'
        },
        secret_name='solr-config',
        interactive=interactive
    )


def initialize_self_hosted(interactive=False):
    get_provider(default=solrcloud_provider_id, verbose=True).initialize()


def get_internal_http_endpoint():
    if is_self_hosted():
        return get_provider().get_internal_http_endpoint()
    else:
        return config_get('http-endpoint', required=True)


def is_self_hosted(config_vals=None):
    if config_vals:
        config_val = config_vals['self-hosted']
    else:
        config_val = config_get('self-hosted', required=True)
    return config_val == 'y'


def get_num_shards():
    return config_get('num-shards')


def get_replication_factor():
    return config_get('replication-factor')


def config_get(key, required=False):
    return config_manager.get(key, secret_name='solr-config', required=required)


def get_provider(default=None, verbose=False):
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, verbose=verbose)


def start_zoonavigator_port_forward():
    get_provider().start_zoonavigator_port_forward()


def start_solrcloud_port_forward(suffix='sc-0'):
    get_provider().start_solrcloud_port_forward(suffix=suffix)


def delete_collection(collection_name):
    solr_curl(f'/admin/collections?action=DELETE&name={collection_name}', required=True)


def get_collectoin_status(collection_name):
    output = solr_curl(f'/{collection_name}/schema')
    if output == False:
        return {'ready': False,
                'collection_name': collection_name,
                'solr_http_endpoint': get_internal_http_endpoint()}
    else:
        res = json.loads(output)
        return {'ready': True,
                'collection_name': collection_name,
                'solr_http_endpoint': get_internal_http_endpoint(),
                'schemaVersion': res['schema']['version'],
                'schemaName': res['schema']['name']}


def create_collection(collection_name, config_name):
    logs.info(f'creating solrcloud collection {collection_name} using config {config_name}')
    replication_factor = get_replication_factor()
    num_shards = get_num_shards()
    output = solr_curl(f'/admin/collections?action=CREATE'
                       f'&name={collection_name}'
                       f'&collection.configName={config_name}'
                       f'&replicationFactor={replication_factor}'
                       f'&numShards={num_shards}', required=True)
    logs.info(output)


def solr_curl(path, required=False, debug=False):
    if is_self_hosted():
        return get_provider().solr_curl(path, required=required, debug=debug)
    else:
        http_endpoint = get_internal_http_endpoint()
        if debug:
            subprocess.check_call(f'curl \'{http_endpoint}{path}\'')
        else:
            exitcode, output = subprocess.getstatusoutput(f'curl -s -f \'{http_endpoint}{path}\'')
            if exitcode == 0:
                return output
            elif required:
                logs.critical(output)
                raise Exception(f'Failed to run solr curl: {http_endpoint}{path}')
            else:
                logs.warning(output)
                return False
