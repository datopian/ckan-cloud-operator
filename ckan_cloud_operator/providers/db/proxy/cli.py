import click

from ckan_cloud_operator import logs

from . import manager


@click.group()
def proxy():
    """Manage the centralized db proxy"""
    pass


@proxy.command()
def port_forward():
    manager.start_port_forward()


@proxy.command()
@click.option('--verify-instance-id')
def proxy_update(verify_instance_id):
    manager.update(wait_updated=not verify_instance_id)
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
