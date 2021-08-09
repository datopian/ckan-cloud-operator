import click

from .helm import cli as helm_cli
from .drone import cli as drone_cli
from .drone import manager


drone_manager = manager.Drone()

@click.group()
def deployment():
    """Manage CKAN instance deployments"""
    pass

@deployment.command()
@click.option('--branch', default='develop', help='Source Branch for build [default: develop]')
def logs(branch):
    """See CKAN instances deployment Logs"""
    drone_manager.initialize()
    drone_manager.builds_logs(branch)


deployment.add_command(helm_cli.helm)
deployment.add_command(drone_cli.drone)
