import click
import time

from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.cluster import manager
from ckan_cloud_operator.labels import manager as labels_manager

from .aws.cli import aws as aws_cli


@click.group()
def cluster():
    """Manage the cluster"""
    pass


cluster.add_command(aws_cli)


@cluster.command()
@click.option('--interactive', is_flag=True)
@click.option('--cluster-provider', default='gcloud')
@click.option('--skip-to')
def initialize(interactive, cluster_provider, skip_to):
    """Initialize the currently connected cluster"""
    manager.initialize(interactive=interactive, default_cluster_provider=cluster_provider, skip_to=skip_to)
    logs.exit_great_success()


@cluster.command()
@click.option('--debug', is_flag=True)
@click.option('--full', is_flag=True)
def info(debug, full):
    manager.print_info(debug=debug, minimal=not full)


@cluster.command()
@click.argument('DISK_SIZE_GB')
def create_volume(disk_size_gb):
    label_prefix = labels_manager.get_label_prefix()
    print(manager.create_volume(
        disk_size_gb,
        {f'{label_prefix}/operator-volume-source': 'cli'}
    ))


@cluster.command()
@click.argument('COMMAND', nargs=-1)
def provider_exec(command):
    manager.provider_exec(' '.join(command))
