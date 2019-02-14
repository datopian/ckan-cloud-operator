import click
import binascii
import os
import yaml

from ckan_cloud_operator import logs

from . import driver


@click.group()
def postgres():
    """Manage PostgreSQL databases unrelated to the operator or cluster"""
    pass


@postgres.command()
@click.option('--db-name')
@click.option('--db-password')
@click.option('--admin-connection-string')
def create_base_db(db_name, db_password, admin_connection_string):
    with _get_admin_connection(admin_connection_string) as admin_conn:
        db_name = db_name or _generate_password(8)
        db_password = db_password or _generate_password(12)
        logs.info(f'creating base db: {db_name} / {db_password}')
        driver.create_base_db(admin_conn, db_name, db_password)
        logs.exit_great_success()


@postgres.command()
@click.option('--db-name')
@click.option('--admin-connection-string')
def db_role_info(db_name, admin_connection_string):
    assert db_name
    with _get_admin_connection(admin_connection_string) as admin_conn:
        print(yaml.dump(driver.get_db_role_info(admin_conn, db_name), default_flow_style=False))


@postgres.command()
@click.option('--admin-connection-string')
@click.option('--full', is_flag=True)
@click.option('--validate', is_flag=True)
def db_names(admin_connection_string, full, validate):
    with _get_admin_connection(admin_connection_string) as admin_conn:
        print(yaml.dump(list(driver.list_db_names(admin_conn, full, validate)), default_flow_style=False))


@postgres.command()
@click.option('--admin-connection-string')
@click.option('--full', is_flag=True)
@click.option('--validate', is_flag=True)
def roles(admin_connection_string, full, validate):
    with _get_admin_connection(admin_connection_string) as admin_conn:
        print(yaml.dump(list(driver.list_roles(admin_conn, full, validate)), default_flow_style=False))


def _get_admin_connection_string(connection_string):
    if connection_string: return connection_string
    from ckan_cloud_operator.providers.db.manager import get_external_admin_connection_string
    return get_external_admin_connection_string()


def _get_admin_connection(connection_string):
    return driver.connect(_get_admin_connection_string(connection_string))


def _generate_password(size):
    return binascii.hexlify(os.urandom(size)).decode()
