import click
import datetime
import traceback
import subprocess

from ckan_cloud_operator import logs

from . import manager

from .gcloudsql import cli as gcloudsql_proxy_cli
from ckan_cloud_operator.config import manager as config_manager


@click.group()
def proxy():
    """Manage the centralized db proxy"""
    pass


proxy.add_command(gcloudsql_proxy_cli.gcloudsql)


@proxy.command()
@click.option('--db-prefix')
@click.option('--all-daemon')
def port_forward(db_prefix, all_daemon):
    if all_daemon:
        assert not db_prefix and all_daemon == 'I know the risks'
        subprocess.Popen(['ckan-cloud-operator', 'db', 'proxy', 'port-forward'], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        for db_prefix in manager.get_provider().get_all_db_prefixes():
            subprocess.Popen(['ckan-cloud-operator', 'db', 'proxy', 'port-forward', '--db-prefix', db_prefix],
                             stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    else:
        while True:
            start_time = datetime.datetime.now()
            try:
                manager.start_port_forward(db_prefix=db_prefix)
            except Exception:
                traceback.print_exc()
            end_time = datetime.datetime.now()
            if (end_time - start_time).total_seconds() < 10:
                logs.critical('DB Proxy failure')
                logs.exit_catastrophic_failure()
            else:
                logs.warning('Restarting the DB proxy')


@proxy.command()
@click.option('--verify-instance-id')
@click.option('--set-pool-mode')
@click.option('--reload', is_flag=True)
def proxy_update(verify_instance_id, set_pool_mode, reload):
    manager.update(wait_updated=reload, set_pool_mode=set_pool_mode)
    if verify_instance_id:
        from ckan_cloud_operator.providers.db import manager as db_manager
        logs.info(f'{verify_instance_id}: Checking DB..')
        db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id))
        logs.info(f'{verify_instance_id}: Checking DataStore..')
        db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id,
                                                                                                    is_datastore=True))
        logs.info(f'{verify_instance_id}: Checking DataStore ReadOnly..')
        db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id,
                                                                                                    is_datastore_readonly=True))
    logs.exit_great_success()


@proxy.command()
def initialize():
    manager.initialize()
    logs.exit_great_success()
