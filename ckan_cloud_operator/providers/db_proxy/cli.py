import click

from ckan_cloud_operator.providers.db_proxy.pgbouncer import cli as pgbouncer_cli


@click.group()
def db_proxy_group():
    """Manage the centralize db proxy providers"""
    pass


db_proxy_group.add_command(pgbouncer_cli.pgbouncer_group, 'pgbouncer')
