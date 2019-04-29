import click

from ckan_cloud_operator import logs

from . import manager


@click.group()
def helm():
    """Manage CKAN instances deployed via Helm"""
    pass


@helm.command()
def initialize():
    manager.initialize()
