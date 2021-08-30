import click

from ckan_cloud_operator import logs

from . import manager


drone_manager = manager.Drone()

@click.group()
def drone():
    """Manage Drone CI/CD"""
    pass


@drone.command()
@click.option('--force-update', default=False, help='Force update drone configurations [default: develop]', is_flag=True)
def initialize(force_update):
    """Initialize drone"""
    drone_manager.initialize(force_update)
