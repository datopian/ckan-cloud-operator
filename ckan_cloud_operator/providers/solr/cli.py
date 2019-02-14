import click
import yaml

from ckan_cloud_operator import logs

from .proxy import cli as proxy_cli


@click.group()
def solr():
    """Manage SOLR"""
    pass


solr.add_command(proxy_cli.proxy)
