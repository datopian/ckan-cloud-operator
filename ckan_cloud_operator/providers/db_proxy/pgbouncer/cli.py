import click

from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.db_proxy.pgbouncer import manager as pgbouncer_manager


@click.group()
def pgbouncer_group():
    """Manage the pgbouncer db-proxy which provides connection pooling"""
    pass


@pgbouncer_group.command()
def initialize():
    """Deploy and enable pgbouncer as the main DB proxy"""
    pgbouncer_manager.initialize()
    pgbouncer_manager.set_as_main_db_proxy()
    logs.exit_great_success()


@pgbouncer_group.command()
def update():
    """Update with all currently enabled instance db details"""
    pgbouncer_manager.update()
    logs.exit_great_success()