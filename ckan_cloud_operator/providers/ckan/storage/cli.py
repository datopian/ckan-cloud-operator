import click
import yaml

from ckan_cloud_operator import logs

from . import manager


@click.group()
def storage():
    """Manage CKAN Storage"""
    pass


@storage.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    manager.initialize(interactive=interactive)
    logs.exit_great_success()


@storage.command()
def deis_minio_bucket_policy():
    print(manager.get_deis_minio_bucket_policy())
    logs.exit_great_success(quiet=True)
