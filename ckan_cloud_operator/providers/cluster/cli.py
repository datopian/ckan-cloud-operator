import click
import time

from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.cluster import manager
from ckan_cloud_operator.labels import manager as labels_manager


@click.group()
def cluster():
    """Manage the centralized db"""
    pass


@cluster.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    """Initialize the currently connected cluster"""
    manager.initialize(interactive=interactive)
    logs.exit_great_success()


@cluster.command()
@click.option('--debug', is_flag=True)
def info(debug):
    manager.print_info(debug=debug)


@cluster.command()
@click.argument('DISK_SIZE_GB')
def create_volume(disk_size_gb):
    label_prefix = labels_manager.get_label_prefix()
    print(manager.create_volume(
        disk_size_gb,
        {f'{label_prefix}/operator-volume-source': 'cli'}
    ))
