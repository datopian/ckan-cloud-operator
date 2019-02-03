import click

from ckan_cloud_operator.providers.db.gcloudsql import cli as gcloudsql_cli


@click.group()
def db_group():
    """Manage the centralize db proxy providers"""
    pass


db_group.add_command(gcloudsql_cli.gcloudsql_group, 'gcloudsql')
