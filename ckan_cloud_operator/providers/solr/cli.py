import click
import yaml

from ckan_cloud_operator import logs

from .proxy import cli as proxy_cli
from . import manager


@click.group()
def solr():
    """Manage SOLR"""
    pass


solr.add_command(proxy_cli.proxy)


@solr.command()
@click.option('--interactive', is_flag=True)
@click.option('--dry-run', is_flag=True)
def initialize(interactive, dry_run):
    manager.initialize(interactive=interactive, dry_run=dry_run)
    logs.exit_great_success()


@solr.command()
def zoonavigator_port_forward():
    manager.start_zoonavigator_port_forward()


@solr.command()
@click.option('--suffix', default='sc-3')
def solrcloud_port_forward(suffix):
    manager.start_solrcloud_port_forward(suffix)


@solr.command()
@click.argument('COLLECTION_NAME')
def collection_status(collection_name):
    logs.print_yaml_dump(manager.get_collection_status(collection_name))


@solr.command()
@click.argument('PATH')
def curl(path):
    print(manager.solr_curl(path, required=True, debug=True))


@solr.command()
def internal_http_endpoint():
    print(manager.get_internal_http_endpoint())


#### ZooKeeper


@click.group()
def zk():
    """Manage ZooKeeper"""
    pass


@zk.command()
@click.option('--config-name')
@click.option('--output-dir')
@click.option('--filename')
@click.option('--all', is_flag=True)
def get_configs(config_name, output_dir, filename, all):
    if config_name:
        config_names = [config_name]
    else:
        config_names = manager.zk_list_configs()
        if not all:
            config_names = [cn for cn in config_names if 'ckan' in cn]
    for zk_config_name in config_names:
        print(f'-- {zk_config_name}')
        if filename:
            config_files = [filename]
        else:
            config_files = []
            manager.zk_list_config_files(zk_config_name, config_files)
        for zk_filename in config_files:
            print(f'/{zk_config_name}{zk_filename}')
            if output_dir:
                output_filename = f'{output_dir}/{zk_config_name}{zk_filename}'
                manager.zk_get_config_file(zk_config_name, zk_filename, output_filename)
                print(f'--> {output_filename}')


@zk.command()
@click.argument('CONFIGS_DIR')
def put_configs(configs_dir):
    manager.zk_put_configs(configs_dir)
    logs.exit_great_success()


solr.add_command(zk)
