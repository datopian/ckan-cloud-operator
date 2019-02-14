import click
import yaml

from ckan_cloud_operator import logs

from . import manager


@click.group()
def crds():
    pass


@crds.command()
def initialize():
    """Interactive initialization of the crds subsystem"""
    manager.initialize()
    logs.exit_great_success()


@crds.command()
@click.option('--full', is_flag=True)
@click.option('--debug', is_flag=True)
def list_crds(full, debug):
    """List the installed crds"""
    for crd in manager.list_crds(full, debug):
        print(yaml.dump([crd], default_flow_style=False))


@crds.command()
@click.argument('SINGULAR')
@click.option('--full', is_flag=True)
@click.option('--debug', is_flag=True)
def get_crd(singular, full, debug):
    """Get metadata for a custom resource definition"""
    print(yaml.dump(manager.get_crd(singular, full, debug), default_flow_style=False))


@crds.command()
@click.option('--singular')
@click.option('--name')
def list_resources(singular, name):
    for resource in manager.list_resources(singular, name):
        print(yaml.dump([resource], default_flow_style=False))
