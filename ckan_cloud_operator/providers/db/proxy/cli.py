import click
import datetime
import traceback

from ckan_cloud_operator import logs

from . import manager


@click.group()
def proxy():
    """Manage the centralized db proxy"""
    pass


@proxy.command()
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
