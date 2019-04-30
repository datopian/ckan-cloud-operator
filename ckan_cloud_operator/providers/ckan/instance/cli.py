import click
import yaml
import json

from ckan_cloud_operator import logs

from . import manager


@click.group()
def instance():
    """Manage CKAN Instances"""
    pass


@instance.command()
@click.argument('INSTANCE_TYPE')
@click.argument('VALUES_FILE')
@click.option('--instance-id')
@click.option('--instance-name')
@click.option('--exists-ok', is_flag=True)
@click.option('--dry-run', is_flag=True)
def create(instance_type, values_file, instance_id, instance_name, exists_ok, dry_run):
    manager.create(instance_id=instance_id, instance_type=instance_type, instance_name=instance_name,
                   values_filename=values_file, exists_ok=exists_ok, dry_run=dry_run)
    logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_ID_OR_NAME')
@click.argument('OVERRIDE_SPEC_JSON', required=False)
@click.option('--persist-overrides', is_flag=True)
@click.option('--wait-ready', is_flag=True)
@click.option('--skip-deployment', is_flag=True)
def update(instance_id_or_name, override_spec_json, persist_overrides, wait_ready, skip_deployment):
    """Update an instance to the latest resource spec, optionally applying the given json override to the resource spec

    Examples:

    ckan-cloud-operator ckan instance update <INSTANCE_ID_OR_NAME> '{"siteUrl": "http://localhost:5000"}' --wait-ready

    ckan-cloud-operator ckan instance update <INSTANCE_ID_OR_NAME> '{"replicas": 3}' --persist-overrides
    """
    override_spec = json.loads(override_spec_json) if override_spec_json else None
    manager.update(instance_id_or_name, override_spec=override_spec, persist_overrides=persist_overrides,
                   wait_ready=wait_ready, skip_deployment=skip_deployment)
    logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_ID_OR_NAME')
@click.argument('ATTR', required=False)
def get(instance_id_or_name, attr):
    """Get detailed information about an instance, optionally returning only a single get attribute

    Example: ckan-cloud-operator ckan instance get <INSTANCE_ID_OR_NAME> deployment
    """
    logs.print_yaml_dump(manager.get(instance_id_or_name, attr), exit_success=True)


@instance.command('list')
@click.option('-f', '--full', is_flag=True)
@click.option('-q', '--quick', is_flag=True)
@click.option('--name')
def list_instances(full, quick, name):
    for instance in manager.list_instances(full=full, quick=quick, name=name):
        logs.print_yaml_dump([instance])
    logs.exit_great_success(quiet=True)


@instance.command()
@click.argument('INSTANCE_ID')
@click.argument('INSTANCE_NAME')
def set_name(instance_id, instance_name):
    logs.info(f'{instance_name} --> {instance_id}')
    manager.set_name(instance_id, instance_name)
    logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_NAME')
def delete_name(instance_name):
    manager.delete_name(instance_name=instance_name)
    logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_ID')
def delete(instance_id):
    manager.delete(instance_id=instance_id)
    logs.exit_great_success()
