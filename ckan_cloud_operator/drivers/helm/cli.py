import click

from . import driver
from ckan_cloud_operator import logs


@click.group()
def helm():
    """Interact with Helm/Tiller"""
    pass


@helm.command()
@click.argument('TILLER_NAMESPACE_NAME')
def init(tiller_namespace_name):
    driver.init(tiller_namespace_name)
    logs.exit_great_success(quiet=True)
