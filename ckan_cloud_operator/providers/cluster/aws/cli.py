import click
import time

from ckan_cloud_operator import logs

from . import manager


@click.group()
def aws():
    """Manage an AWS cluster"""
    pass


@aws.command()
def get_storage_availability_zone():
    az = manager.get_storage_availability_zone()
    assert az, "No default storage availability zone, please set a zone using 'ckan-cloud-operator cluster aws set-storage-availability-zone'"
    print(az)


@aws.command()
@click.argument('ZONE', required=False)
def set_storage_availability_zone(zone):
    if not zone:
        zone = manager.auto_get_availability_zone()
        print(f'Using availability zone: {zone}')
    manager.set_storage_availability_zone(zone)


@aws.command()
@click.argument('SUB_DOMAIN')
@click.argument('ROOT_DOMAIN')
@click.argument('LOAD_BALANCER_HOSTNAME')
def update_dns_record(sub_domain, root_domain, load_balancer_hostname):
    manager.update_dns_record(sub_domain, root_domain, load_balancer_hostname)
    logs.exit_great_success()
