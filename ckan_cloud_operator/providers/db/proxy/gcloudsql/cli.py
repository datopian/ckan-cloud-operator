import click
import datetime
import traceback

from ckan_cloud_operator import logs

from . import manager


@click.group()
def gcloudsql():
    """Manage the gcloudsql centralized db proxy"""
    pass


@gcloudsql.command()
def port_forward():
    while True:
        start_time = datetime.datetime.now()
        try:
            manager.start_port_forward()
        except Exception:
            traceback.print_exc()
        end_time = datetime.datetime.now()
        if (end_time - start_time).total_seconds() < 10:
            logs.critical('DB Proxy failure')
            logs.exit_catastrophic_failure()
        else:
            logs.warning('Restarting the DB proxy')


@gcloudsql.command()
def initialize():
    manager.initialize()
    logs.exit_great_success()
