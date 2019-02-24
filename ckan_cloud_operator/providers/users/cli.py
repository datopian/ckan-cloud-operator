import click
import yaml

from ckan_cloud_operator import logs
from . import manager


@click.group()
def users():
    pass


@users.command()
def initialize():
    manager.initialize()
    logs.exit_great_success()


@users.command()
@click.argument('USER_NAME')
def get_kubeconfig(user_name):
    """Get kubeconfig file for a user"""
    print(yaml.dump(manager.get_kubeconfig(user_name), default_flow_style=False))
    logs.exit_great_success(quiet=True)


@users.command()
@click.argument('USER_NAME')
@click.option('--role')
def create(user_name, role):
    """Create a user with the given role"""
    manager.create(user_name, role)
    manager.update(user_name)
    logs.exit_great_success()
