import subprocess
import json
import os
import glob
import time

from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

from .constants import PROVIDER_SUBMODULE
from .solrcloud.constants import PROVIDER_ID as solrcloud_provider_id


def initialize(interactive=False, dry_run=False):
    ckan_infra = CkanInfra(required=False)
    solr_config = config_manager.interactive_set(
        {
            'self-hosted': True
        },
        secret_name='solr-config',
        interactive=interactive
    )
    if is_self_hosted(solr_config):
        initialize_self_hosted(interactive=interactive, dry_run=dry_run)
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


def initialize_self_hosted(interactive=False, dry_run=False):
    get_provider(default=solrcloud_provider_id, verbose=True).initialize(interactive=interactive, dry_run=dry_run)
    zk_set_url_scheme()


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
    from ckan_cloud_operator.providers import manager as providers_manager
    return providers_manager.get_provider(PROVIDER_SUBMODULE, default=default, verbose=verbose)


def start_zoonavigator_port_forward():
    get_provider().start_zoonavigator_port_forward()


def start_solrcloud_port_forward(suffix='sc-0'):
    get_provider().start_solrcloud_port_forward(suffix=suffix)


def delete_collection(collection_name):
    solr_curl(f'/admin/collections?action=DELETE&name={collection_name}', required=True)


def get_collection_status(collection_name):
    output = solr_curl(f'/{collection_name}/schema')
    if output == False:
        return {'ready': False,
                'collection_name': collection_name,
                'solr_http_endpoint': get_internal_http_endpoint()}
    else:
        def_ver, def_name = '2.8', 'ckan'
        res = {'schema': {'version': def_ver, 'name': def_name}}
        try:
            res = json.loads(output)
        except json.decoder.JSONDecodeError as e:
            logs.warning(
                f'Not able to decode response from SOLR. Using default values for schema version/name - {def_ver}/{def_name}\n SOLR response: \n{output}'
            )

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

def zk_set_url_scheme(scheme='http', timeout=300):
    pod_name = kubectl.get('pods', '-l', 'app=provider-solr-solrcloud-zk', required=True)['items'][0]['metadata']['name']
    try:
        kubectl.check_output('exec %s zkCli.sh set /clusterprops.json \'{"urlScheme":"%s"}\'' % (pod_name, scheme))
    except Exception as e:
        print('Failed to connect ZooKeeper, retrying in 60 seconds')
        time.sleep(60)
        if timeout < 0:
            raise e
        zk_set_url_scheme(scheme=scheme, timeout=timeout-60)


def zk_list_configs():
    pod_name = kubectl.get('pods', '-l', 'app=provider-solr-solrcloud-zk', required=True)['items'][0]['metadata']['name']
    lines = list(kubectl.check_output(f'exec {pod_name} zkCli.sh ls /configs').decode().splitlines())[5:]
    if len(lines) == 1:
        return [name.strip() for name in lines[0][1:-1].split(',')]
    else:
        return []


def zk_list_config_files(config_name, config_files, base_path=''):
    path = f'/configs/{config_name}{base_path}'
    # print(f'path={path}')
    pod_name = kubectl.get('pods', '-l', 'app=provider-solr-solrcloud-zk', required=True)['items'][0]['metadata']['name']
    lines = list(kubectl.check_output(f'exec {pod_name} zkCli.sh ls {path}').decode().splitlines())[5:]
    # print(f'lines={lines}')
    assert len(lines) == 1
    num_files = 0
    for name in lines[0][1:-1].split(','):
        name = name.strip()
        if not name: continue
        # print(f'name={name}')
        if zk_list_config_files(config_name, config_files, base_path=f'{base_path}/{name}') == 0:
            config_files.append(f'{base_path}/{name}')
            num_files += 1
    return num_files


def zk_get_config_file(config_name, config_file, output_filename):
    path = f'/configs/{config_name}{config_file}'
    # print(f'path={path}')
    pod_name = kubectl.get('pods', '-l', 'app=provider-solr-solrcloud-zk', required=True)['items'][0]['metadata']['name']
    lines = list(kubectl.check_output(f'exec {pod_name} zkCli.sh get {path} 2>/dev/null').decode().splitlines())[5:]
    assert len(lines) > 0
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, 'w') as f:
        f.write('\n'.join(lines))


def zk_put_configs(configs_dir):
    def retry_if_fails(command, max_retries=15):
        if max_retries < 0:
            return
        try:
            kubectl.check_output(command)
        except:
            time.sleep(5)
            retry_if_fails(command, max_retries=max_retries-1)

    pod_name = kubectl.get('pods', '-l', 'app=provider-solr-solrcloud-zk', required=True)['items'][0]['metadata']['name']
    logs.info(f'using pod {pod_name}')
    for input_filename in glob.glob(f'{configs_dir}/**/*', recursive=True):
        if not os.path.isfile(input_filename): continue
        output_filename = '/configs' + input_filename.replace(configs_dir, '')
        logs.info(f'{input_filename} --> {output_filename}')
        output_filepath = ''
        for output_filepart in output_filename.split('/')[:-1]:
            output_filepart = output_filepart.strip()
            if not output_filepart:
                continue
            output_filepath += f'/{output_filepart}'
            logs.info(f'create {output_filepath} null')
            retry_if_fails(f'exec {pod_name} zkCli.sh create {output_filepath} null')
        logs.info(f'copy {output_filename}')
        retry_if_fails(f'cp {input_filename} {pod_name}:/tmp/zk_input')
        logs.info(f'create {output_filename}')
        retry_if_fails(f"exec {pod_name} -- /bin/bash -c '/usr/bin/zkCli.sh create {output_filename} \"$(cat /tmp/zk_input)\"'")
