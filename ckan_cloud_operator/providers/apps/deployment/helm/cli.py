import click

from ckan_cloud_operator import logs

from . import manager


@click.group()
def helm():
    """Manage App instances deployed using Helm"""
    pass


@helm.command()
def initialize():
    logs.exit_great_success()


@helm.command()
@click.option('--tiller-namespace-name')
@click.option('--chart-repo')
@click.option('--chart-version')
@click.option('--chart-release-name')
@click.option('--values-json')
@click.option('--values-filename')
@click.option('--instance-id')
@click.option('--instance-name')
@click.option('--exists-ok', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--update', 'update_', is_flag=True)
@click.option('--wait-ready', is_flag=True)
@click.option('--skip-deployment', is_flag=True)
@click.option('--skip-route', is_flag=True)
@click.option('--force', is_flag=True)
@click.option('--app-type')
def create(**kwargs):
    instance_id = manager.create(**kwargs)
    logs.info(f'\n\nCreated instance ID: \n\n{instance_id}\n\n')
    logs.exit_great_success()
