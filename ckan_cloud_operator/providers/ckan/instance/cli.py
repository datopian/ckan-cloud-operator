import click
import yaml
import json
import traceback

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

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
@click.option('--update', 'update_', is_flag=True)
@click.option('--wait-ready', is_flag=True)
@click.option('--skip-deployment', is_flag=True)
@click.option('--skip-route', is_flag=True)
@click.option('--force', is_flag=True)
def create(instance_type, values_file, instance_id, instance_name, exists_ok, dry_run, update_, wait_ready,
           skip_deployment, skip_route, force):
    '''
    Create CKAN instance
    '''
    manager.create(instance_id=instance_id, instance_type=instance_type, instance_name=instance_name,
                   values_filename=values_file, exists_ok=exists_ok, dry_run=dry_run, update_=update_,
                   wait_ready=wait_ready, skip_deployment=skip_deployment, skip_route=skip_route, force=force)

    logs.exit_great_success()


@instance.command()
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

    ckan-cloud-operator ckan instance update <INSTANCE_ID_OR_NAME> '{"siteUrl": "http://localhost:5000"}' --wait-ready

    ckan-cloud-operator ckan instance update <INSTANCE_ID_OR_NAME> '{"replicas": 3}' --persist-overrides
    """
    override_spec = json.loads(override_spec_json) if override_spec_json else None
    manager.update(instance_id_or_name, override_spec=override_spec, persist_overrides=persist_overrides,
                   wait_ready=wait_ready, skip_deployment=skip_deployment, skip_route=skip_route,
                   force=force)
    logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_ID_OR_NAME')
@click.argument('ATTR', required=False)
@click.option('--with-spec', is_flag=True)
def get(instance_id_or_name, attr, with_spec):
    """Get detailed information about an instance, optionally returning only a single get attribute

    Example: ckan-cloud-operator ckan instance get <INSTANCE_ID_OR_NAME> deployment
    """
    if attr == 'spec':
        with_spec = True
    logs.print_yaml_dump(manager.get(instance_id_or_name, attr, with_spec=with_spec), exit_success=True)


@instance.command()
@click.argument('INSTANCE_ID_OR_NAME')
def edit(instance_id_or_name):
    '''Edit CKAN instance
    '''
    manager.edit(instance_id_or_name)


@instance.command('list')
@click.option('-f', '--full', is_flag=True)
@click.option('-q', '--quick', is_flag=True)
@click.option('-c', '--credentials', is_flag=True)
@click.option('--name')
def list_instances(full, quick, name, credentials):
    '''
    List existing CKAN instaces
    '''
    instances = list(
        manager.list_instances(full=full, quick=quick,
                               name=name, withCredentials=credentials)
    )
    logs.print_yaml_dump(instances)
    logs.exit_great_success(quiet=True)


# @instance.command()
# @click.argument('INSTANCE_ID')
# @click.argument('INSTANCE_NAME')
# def set_name(instance_id, instance_name):
#     logs.info(f'{instance_name} --> {instance_id}')
#     manager.set_name(instance_id, instance_name)
#     logs.exit_great_success()


@instance.command()
@click.argument('INSTANCE_ID_OR_NAME', nargs=-1)
@click.option('--no-dry-run', is_flag=True)
def delete(instance_id_or_name, no_dry_run):
    '''
    Delete CKAN instance
    '''
    generator = manager.delete_instances(instance_ids_or_names=instance_id_or_name, dry_run=not no_dry_run)
    while True:
        try:
            logs.info('Deleting instance', **next(generator))
        except StopIteration:
            break
        logs.info(**next(generator))
    logs.exit_great_success(quiet=True)


# @instance.command()
# @click.argument('INSTANCE_NAME')
# def delete_name(instance_name):
#     manager.delete_name(instance_name=instance_name)
#     logs.exit_great_success()
#
#
## Moved to `sysadmin`
# @instance.command()
# @click.argument('INSTANCE_ID_OR_NAME')
# @click.argument('NAME')
# @click.argument('EMAIL', required=False)
# @click.argument('PASSWORD', required=False)
# @click.option('--dry-run', is_flag=True)
# def create_ckan_admin_user(instance_id_or_name, name, email, password, dry_run):
#     logs.print_yaml_dump(manager.create_ckan_admin_user(instance_id_or_name, name, email, password, dry_run))
#     logs.exit_great_success()



@instance.command('logs')
@click.option('--service', help='Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`')
@click.option('--since', help='Only return logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs.')
@click.option('--follow', help='Specify if the logs should be streamed.')
@click.option('--tail', help='Lines of recent log file to display. Defaults to -1 with no selector, showing all log lines otherwise 10, if a selector is provided.')
@click.option('--container', help='Conainer name if multiple')
@click.option('--grep', help='Filter logs by the given word (case insensitive)')
def ckan_logs(command):
    '''
    Check CKAN and other service container logs
    '''
    pass


@instance.command('ckan-exec')
@click.argument('INSTANCE_ID')
@click.option('--command', help='command to pass down to ckan CLI, without path to config file')
@click.option('--use-paster', help='Use paster over ckan CLI (supported in ckan v2.9)', default=False)
def ckan_exec(instance_id, command, use_paster):
    '''
    Executes ckan CLI commands

    See full list of command in [CKAN Docs](https://docs.ckan.org/en/2.9/maintaining/cli.html#ckan-commands-reference). You will need to pass full command as a string

    \b
    cco ckan instance ckan-exec --command='view clean --yes'
    cco ckan instance ckan-exec --command='jobs list'
    cco ckan instance ckan-exec --command='dataset show dataset-id'
    '''
    manager.run_ckan_commands(instance_id, command)


@instance.command('ssh')
@click.option('--service', help='Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`')
@click.option('--command', help='One of `bash`, `sh`. Defaults to `bash`')
def ckan_ssh(service, command):
    '''
    SSH into the running container.
    '''
    pass


@instance.command('shell')
@click.option('--service', help='Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`')
@click.option('--command', help='One of `bash`, `sh`. Defaults to `bash`')
def ckan_shell(service, command):
    '''
    Run Unix-like operating system commands into the running container

    cco ckan instance shell --command='cat /etc/ckan/production.ini'
    '''
    pass


@click.group()
def sysadmin():
    """Create or delete system administrator for CKAN instance"""
    pass

instance.add_command(sysadmin)


@sysadmin.command('add')
@click.argument('INSTANCE_ID')
@click.option('--username', required=True, help='User name for user if user does not exist')
@click.option('--password', help='Password for user if user does not exist')
@click.option('--email', help='Valid Email address for user if user does not exist')
@click.option('--use-paster', help='Use paster over ckan CLI (supported in ckan v2.9)', default=False)
def sysadmin_add(instance_id, username, password, email, use_paster):
    '''
    Creates or makes given user system administrator

    cco ckan instance sysadmin add USERNAME --pasword pasword --email email@email.com
    '''
    manager.create_ckan_admin_user(instance_id, username, password, email, use_paster)


@sysadmin.command('rm')
@click.argument('INSTANCE_ID')
@click.option('--username', required=True, help='Passowrd for user if user does not exist')
@click.option('--use-paster', help='Use paster over ckan CLI (supported in ckan v2.9)', default=False)
def sysadmin_rm(instance_id, username, use_paster):
    '''
    Removes System administrator privileges from given user

    cco ckan instance sysadmin rm USERNAME
    '''
    manager.delete_ckan_admin_user(instance_id, username, use_paster)


@click.group()
def solr():
    """Update, clear or check search index for CKAN instance"""
    pass

instance.add_command(solr)


@solr.command('check')
@click.argument('INSTANCE_ID')
def solr_check(instance_id):
    '''
    Check the search index
    '''
    manager.run_solr_commands(instance_id, 'check')

@solr.command('clear')
@click.argument('INSTANCE_ID')
def solr_clear(instance_id):
    '''
    Clear the search index
    '''
    manager.run_solr_commands(instance_id, 'clear')

@solr.command('rebuild')
@click.argument('INSTANCE_ID')
def solr_rebuild(instance_id):
    '''
    Rebuild search index
    '''
    manager.run_solr_commands(instance_id, 'rebuild')

@solr.command('rebuild-fast')
@click.argument('INSTANCE_ID')
def solr_rebuild_fast(instance_id):
    '''
    Reindex with multiprocessing
    '''
    manager.run_solr_commands(instance_id, 'check')

@solr.command('show')
@click.argument('INSTANCE_ID')
@click.option('--dataset-id', help='Dataset name to show index for')
def solr_show(instance_id, dataset_id):
    '''
    show --dataset-id=dataset-id-or-name
    '''
    manager.run_solr_commands(instance_id, 'show', dataset_id=dataset_id)

@click.group()
def deployment():
    """Create, Deploy and manage CKAN instances on Kubernetes Cluster"""
    pass

instance.add_command(deployment)

@deployment.command('status')
def deployment_status():
    '''
    Shows status of the deployment. Result of `helm status release-name`
    '''


@deployment.command('logs')
def deployment_logs():
    '''
    Shows deployment logs
    '''

@deployment.command('version')
def deployment_version():
    '''
    Shows version of the latest successful deployment. Same as https://site-url/version
    '''


@click.group('image')
def deployment_image():
    '''
    Create, Deploy and manage CKAN instances on Kubernetes Cluster
    '''
    pass

deployment.add_command(deployment_image)

@deployment_image.command('get')
@click.option('--service', help='Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`')
def deployment_image_get(service):
    '''
    Get and set CKAN or Related service images.
    '''

@deployment_image.command('set')
@click.argument('IMAGE_NAME')
@click.option('--service', help='Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`')
def deployment_image_set(image_name, service):
    '''
    Force set given image for the given service
    '''


@click.group()
def infra():
    '''
    Manage and debug CKAN related infrastructure like SOLR Cloud and Postgres Databases
    '''
    pass

instance.add_command(infra)


@click.group('solr')
def deployment_solr():
    '''
    Check logs of SolrCloud service and restart them.
    '''
    pass

infra.add_command(deployment_solr)


@deployment_solr.command('logs')
@click.option('--zookeper-only', help='Make operations only for zookeper pods', is_flag=True)
@click.option('--solrcloud-only', help='Make operations only for solrcloud pods', is_flag=True)
@click.option('--since', help='Only return logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs.')
@click.option('--follow', help='Specify if the logs should be streamed.')
@click.option('--tail', help='Lines of recent log file to display. Defaults to -1 with no selector, showing all log lines otherwise 10, if a selector is provided.')
@click.option('--container', help='Conainer name if multiple')
@click.option('--grep', help='Filter logs by the given word (case insensitive)')
def infra_solr_logs(zookeper_only, solrcloud_only, since, follow, tail, container, grep):
    '''
    See logs of SolrCloud and ZooKeeper containers
    '''
    pass


@deployment_solr.command('restart')
@click.option('--zookeper-only', help='Make operations only for zookeper pods', is_flag=True)
@click.option('--solrcloud-only', help='Make operations only for solrcloud pods', is_flag=True)
def infra_solr_restart(zookeper_only, solrcloud_only):
    '''
    Restart SolrCloud and Zookeeper containers
    '''
    pass


@click.group('db')
def deployment_db():
    '''
    Get database connection string
    '''
    pass

infra.add_command(deployment_db)


@deployment_db.command('get')
def infra_solr_restart():
    '''
    Get master connection string for ckan Database
    '''
    pass
