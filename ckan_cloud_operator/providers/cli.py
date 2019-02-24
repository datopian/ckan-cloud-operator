import click
import yaml

from . import manager


@click.group('providers')
def providers_group():
    """Manage configurable providers of centralized infrastructure services"""
    pass


@providers_group.command()
def list_providers():
    print(yaml.dump(manager.list_providers(), default_flow_style=False))
