import click

from .helm import cli as helm_cli
from .drone import cli as drone_cli
from .drone import manager
from ckan_cloud_operator.providers.ckan.deployment import manager as deployment_manager
from ckan_cloud_operator.drivers.helm import driver as helm_driver

drone_manager = manager.Drone()

@click.group()
def deployment():
    """Manage CKAN instance deployments"""
    pass

@click.group()
def image():
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


@image.command()
@click.argument('instance-id')
@click.option('--service', default='ckan', help='Micro service name [default: ckan]')
def get(instance_id, service):
    """Get image name for instances"""
    deployment_manager.get_image(instance_id, service=service)


@image.command()
@click.argument('instance-id')
@click.argument('image-name')
@click.option('--service', default='ckan', help='Micro service name [default: ckan]')
@click.option('--container-name', help='Container name to set image for [default: same as service]')
def set(instance_id, image_name, service, container_name):
    """Set image for instance container"""
    deployment_manager.set_image(instance_id, image_name, service=service, container_name=container_name)


deployment.add_command(helm_cli.helm)
deployment.add_command(drone_cli.drone)
deployment.add_command(image)
