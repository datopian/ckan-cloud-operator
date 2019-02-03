import click

from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager


@click.group()
def gcloudsql_group():
    """Manage Google Cloud SQL instances for centralized DB services"""
    pass


@gcloudsql_group.command()
def initialize():
    """Enable Google Cloud SQL as the main DB provider"""
    gcloudsql_manager.initialize()
    gcloudsql_manager.set_as_main_db()
    logs.exit_great_success()
