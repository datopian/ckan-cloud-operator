import click

from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.db.gcloudsql import manager


@click.group('gcloudsql')
def gcloudsql_group():
    """Manage Google Cloud SQL instances for centralized DB services"""
    pass


@gcloudsql_group.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    """Enable Google Cloud SQL as the main DB provider"""
    manager.initialize(interactive=interactive)
    logs.exit_great_success()
