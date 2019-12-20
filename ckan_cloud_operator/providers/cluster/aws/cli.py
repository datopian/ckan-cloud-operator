import click
import time

from ckan_cloud_operator import logs

from . import manager


@click.group()
def aws():
    """Manage an AWS cluster"""
    pass


@aws.command()
@click.argument('SUB_DOMAIN')
@click.argument('ROOT_DOMAIN')
@click.argument('LOAD_BALANCER_HOSTNAME')
def update_dns_record(sub_domain, root_domain, load_balancer_hostname):
    manager.update_dns_record(sub_domain, root_domain, load_balancer_hostname)
    logs.exit_great_success()
