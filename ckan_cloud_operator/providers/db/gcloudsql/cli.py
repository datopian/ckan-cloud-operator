import click

from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.db.gcloudsql import manager


@click.group('gcloudsql')
def gcloudsql_group():
    """Manage Google Cloud SQL instances for centralized DB services"""
    pass


@gcloudsql_group.command()
@click.option('--interactive', is_flag=True)
@click.option('--db-prefix')
def initialize(interactive, db_prefix):
    """Enable Google Cloud SQL as the main DB provider"""
    manager.initialize(interactive=interactive, db_prefix=db_prefix)
    logs.exit_great_success()



@gcloudsql_group.command()
@click.argument('OPERATION_ID')
def operation_status(operation_id):
    logs.print_yaml_dump(manager.get_operation_status(operation_id))


@gcloudsql_group.command()
@click.argument('DATABASE')
@click.argument('CONNECTION_STRING', required=False)
@click.option('--db-prefix')
@click.option('--dry-run', is_flag=True)
def create_backup(database, connection_string, db_prefix, dry_run):
    manager.create_backup(database, connection_string, db_prefix=db_prefix, dry_run=dry_run)
    logs.exit_great_success()


@gcloudsql_group.command()
@click.option('--db-prefix')
@click.option('--dry-run', is_flag=True)
def create_all_backups(db_prefix, dry_run):
    manager.create_all_backups(db_prefix, dry_run=dry_run)
    logs.exit_great_success()
