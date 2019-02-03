import click

from ckan_cloud_operator.providers.db_proxy import cli as db_proxy_cli
from ckan_cloud_operator.providers.db import cli as db_cli


@click.group()
def providers_group():
    """Manage configurable providers of centralized infrastructure services"""
    pass


providers_group.add_command(db_proxy_cli.db_proxy_group, 'db-proxy')
providers_group.add_command(db_cli.db_group, 'db')
