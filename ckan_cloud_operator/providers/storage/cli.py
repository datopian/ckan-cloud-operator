import click
import yaml

from ckan_cloud_operator import logs

from . import manager


@click.group()
def storage():
    """Manage the centralized storage"""
    pass


@storage.command()
@click.option('--interactive', is_flag=True)
@click.option('--provider-id')
@click.option('--storage-suffix')
@click.option('--disk-name')
@click.option('--dry-run', is_flag=True)
def initialize(interactive, provider_id, storage_suffix, disk_name, dry_run):
    manager.initialize(interactive=interactive,
                       provider_id=provider_id,
                       storage_suffix=storage_suffix,
                       use_existing_disk_name=disk_name,
                       dry_run=dry_run)
    logs.exit_great_success()

@storage.command()
@click.option('--raw', is_flag=True)
@click.option('--provider-id')
@click.option('--storage-suffix')
def credentials(raw, provider_id, storage_suffix):
    manager.print_credentials(raw, provider_id=provider_id, storage_suffix=storage_suffix)
