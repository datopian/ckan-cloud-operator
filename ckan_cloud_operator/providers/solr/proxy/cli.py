import click
import yaml

from ckan_cloud_operator import logs

from . import manager


@click.group()
def proxy():
    """Manage SOLR proxy for centralized unauthenticated access"""
    pass


@proxy.command()
def initialize():
    manager.deploy()
    logs.exit_great_success()
