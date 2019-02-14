import click
import yaml

from ckan_cloud_operator import logs

from . import manager


@click.group()
def storage():
    """Manage the centralized storage"""
    pass


@storage.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    manager.initialize(interactive=interactive)
    logs.exit_great_success()

@storage.command()
def credentials():
    manager.print_credentials()
