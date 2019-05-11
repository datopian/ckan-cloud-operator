import click
import json

from ckan_cloud_operator import logs
from .deployment import cli as deployment_cli
from . import manager


@click.group()
def apps():
    """Manage Generic Application Instances"""
    pass


apps.add_command(deployment_cli.deployment)


@apps.command()
def initialize():
    manager.initialize()
    logs.exit_great_success()


@apps.command()
@click.argument('VALUES_FILE')
@click.option('--instance-id')
@click.option('--instance-name')
@click.option('--exists-ok', is_flag=True)
@click.option('--dry-run', is_flag=True)
@click.option('--update', 'update_', is_flag=True)
@click.option('--wait-ready', is_flag=True)
@click.option('--skip-deployment', is_flag=True)
@click.option('--skip-route', is_flag=True)
@click.option('--force', is_flag=True)
def create(values_file, instance_id, instance_name, exists_ok, dry_run, update_, wait_ready,
           skip_deployment, skip_route, force):
    manager.create(instance_id=instance_id, instance_name=instance_name,
                   values_filename=values_file, exists_ok=exists_ok, dry_run=dry_run, update_=update_,
                   wait_ready=wait_ready, skip_deployment=skip_deployment, skip_route=skip_route, force=force)
    logs.exit_great_success()


@apps.command()
@click.argument('INSTANCE_ID_OR_NAME')
@click.argument('OVERRIDE_SPEC_JSON', required=False)
@click.option('--persist-overrides', is_flag=True)
@click.option('--wait-ready', is_flag=True)
@click.option('--skip-deployment', is_flag=True)
@click.option('--skip-route', is_flag=True)
@click.option('--force', is_flag=True)
def update(instance_id_or_name, override_spec_json, persist_overrides, wait_ready, skip_deployment, skip_route, force):
    """Update an instance to the latest resource spec, optionally applying the given json override to the resource spec

    Examples:

    ckan-cloud-operator apps update <INSTANCE_ID_OR_NAME> '{"siteUrl": "http://localhost:5000"}' --wait-ready

    ckan-cloud-operator apps update <INSTANCE_ID_OR_NAME> '{"replicas": 3}' --persist-overrides
    """
    override_spec = json.loads(override_spec_json) if override_spec_json else None
    manager.update(instance_id_or_name, override_spec=override_spec, persist_overrides=persist_overrides,
                   wait_ready=wait_ready, skip_deployment=skip_deployment, skip_route=skip_route,
                   force=force)
    logs.exit_great_success()


@apps.command()
@click.argument('INSTANCE_ID_OR_NAME')
@click.argument('ATTR', required=False)
@click.option('--with-spec', is_flag=True)
def get(instance_id_or_name, attr, with_spec):
    """Get detailed information about an instance, optionally returning only a single get attribute

    Example: ckan-cloud-operator apps get <INSTANCE_ID_OR_NAME> deployment
    """
    if attr == 'spec':
        with_spec = True
    logs.print_yaml_dump(manager.get(instance_id_or_name, attr, with_spec=with_spec), exit_success=True)


@apps.command()
@click.argument('INSTANCE_ID_OR_NAME')
def edit(instance_id_or_name):
    manager.edit(instance_id_or_name)


@apps.command('list')
@click.option('-f', '--full', is_flag=True)
@click.option('-q', '--quick', is_flag=True)
@click.option('--name')
def list_instances(full, quick, name):
    for instance in manager.list_instances(full=full, quick=quick, name=name):
        logs.print_yaml_dump([instance])
    logs.exit_great_success(quiet=True)


@apps.command()
@click.argument('INSTANCE_ID')
@click.argument('INSTANCE_NAME')
def set_name(instance_id, instance_name):
    logs.info(f'{instance_name} --> {instance_id}')
    manager.set_name(instance_id, instance_name)
    logs.exit_great_success()


@apps.command()
@click.argument('INSTANCE_NAME')
def delete_name(instance_name):
    manager.delete_name(instance_name=instance_name)
    logs.exit_great_success()


@apps.command()
@click.argument('INSTANCE_ID_OR_NAME', nargs=-1)
@click.option('--no-dry-run', is_flag=True)
def delete(instance_id_or_name, no_dry_run):
    generator = manager.delete_instances(instance_ids_or_names=instance_id_or_name, dry_run=not no_dry_run)
    while True:
        try:
            logs.info('Deleting instance', **next(generator))
        except StopIteration:
            break
        logs.info(**next(generator))
    logs.exit_great_success(quiet=True)
