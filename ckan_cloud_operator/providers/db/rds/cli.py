import click

from ckan_cloud_operator import logs
from . import manager


@click.group('rds')
def rds():
    """Manage AWS RDS instances for centralized DB services"""
    pass


@rds.command()
@click.option('--interactive', is_flag=True)
@click.option('--db-prefix')
def initialize(interactive, db_prefix):
    """Enable RDS as the main DB provider"""
    manager.initialize(interactive=interactive, db_prefix=db_prefix)
    logs.exit_great_success()
