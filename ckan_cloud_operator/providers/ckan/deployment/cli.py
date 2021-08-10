import click

from .helm import cli as helm_cli
from .drone import cli as drone_cli
from .drone import manager
from ckan_cloud_operator.providers.ckan.deployment import manager as deployment_manager

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


@deployment.command()
@click.argument('instance-id')
def status(instance_id):
    """See CKAN instances deployment status"""
    helm_driver.check_status(instance_id)


@deployment.command()
@click.argument('instance-id')
def version(instance_id):
    """See CKAN instances deployment version"""
    deployment_manager.get_deployment_version(instance_id)

deployment.add_command(helm_cli.helm)
deployment.add_command(drone_cli.drone)
