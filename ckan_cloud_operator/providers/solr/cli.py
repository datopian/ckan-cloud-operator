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
    logs.print_yaml_dump(manager.get_collectoin_status(collection_name))


@solr.command()
@click.argument('PATH')
def curl(path):
    print(manager.solr_curl(path, required=True, debug=True))
