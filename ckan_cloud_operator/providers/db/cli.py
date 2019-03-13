import click
import time
import yaml

from ckan_cloud_operator import logs

from . import manager as db_manager

from .gcloudsql import cli as gcloudsql_cli
from .proxy import cli as proxy_cli
from .web_ui import cli as web_ui_cli


@click.group('db')
def db_group():
    """Manage the centralized db"""
    pass


db_group.add_command(gcloudsql_cli.gcloudsql_group, 'gcloudsql')
db_group.add_command(proxy_cli.proxy)
db_group.add_command(web_ui_cli.web_ui)


@db_group.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    db_manager.initialize(interactive=interactive)


@db_group.command()
@click.option('--admin', is_flag=True)
@click.option('--deis-instance')
@click.option('--datastore', is_flag=True)
@click.option('--datastore-ro', is_flag=True)
@click.option('--db-prefix')
def connection_string(admin, deis_instance, datastore, datastore_ro, db_prefix):
    """Get a DB connection string

    Example: psql -d $(ckan-cloud-operator db connection-string --admin)
    """
    if deis_instance:
        print(db_manager.get_deis_instsance_external_connection_string(deis_instance, is_datastore=datastore,
                                                                       is_datastore_readonly=datastore_ro,
                                                                       admin=admin, db_prefix=db_prefix))
    elif admin:
        assert not deis_instance and not datastore and not datastore_ro
        print(db_manager.get_external_admin_connection_string(db_prefix=db_prefix))
    else:
        raise Exception('invalid arguments')


@db_group.command()
def get_all_dbs_users():
    dbs, users = db_manager.get_all_dbs_users()
    print(yaml.dump({
        'dbs': [' | '.join(map(str, db)) for db in dbs],
        'users': [' | '.join(map(str, user)) for user in users]
    }, default_flow_style=False))
