import click
import time

from ckan_cloud_operator.db import manager as db_manager


@click.group()
def db_group():
    """Manage the centralized db"""
    pass


@db_group.command()
@click.option('--initialize', is_flag=True)
def web_ui(initialize):
    """Start a web-UI for db management"""
    if initialize:
        db_manager.initialize_web_ui()
        time.sleep(5)
    db_manager.web_ui()


@db_group.command()
@click.option('--admin', is_flag=True)
@click.option('--deis-instance')
@click.option('--datastore', is_flag=True)
@click.option('--datastore-ro', is_flag=True)
def connection_string(admin, deis_instance, datastore, datastore_ro):
    """Get a DB connection string

    Example: psql -d $(ckan-cloud-operator db connection-string --admin)
    """
    if admin:
        assert not deis_instance and not datastore and not datastore_ro
        print(db_manager.get_external_admin_connection_string())
    elif deis_instance:
        assert not admin
        print(db_manager.get_deis_instsance_external_connection_string(deis_instance, is_datastore=datastore,
                                                                       is_datastore_readonly=datastore_ro))
    else:
        raise Exception('invalid arguments')
