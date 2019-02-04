import click
import time
import tempfile
import traceback
import os
import subprocess
import yaml

from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
from ckan_cloud_operator.infra import CkanInfra

import ckan_cloud_operator.routers.cli
import ckan_cloud_operator.users
import ckan_cloud_operator.datapushers
import ckan_cloud_operator.manager
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator import gcloud
import ckan_cloud_operator.storage
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers import cli as providers_cli
from ckan_cloud_operator.db import cli as db_cli


CLICK_CLI_MAX_CONTENT_WIDTH = 200


def great_success(**kwargs):
    logs.info('Great Success!', **kwargs)
    exit(0)


@click.group(context_settings={'max_content_width': CLICK_CLI_MAX_CONTENT_WIDTH})
def main():
    """Manage, provision and configure CKAN Clouds and related infrastructure"""
    pass


main.add_command(providers_cli.providers_group, 'providers')
main.add_command(db_cli.db_group, 'db')


@main.command('cluster-info')
@click.option('-f', '--full', is_flag=True)
def __cluster_info(full):
    """Get information about the cluster"""
    ckan_cloud_operator.manager.print_cluster_info(full)


@main.command('install-crds')
def __install_crds():
    """Install ckan-cloud-operator custom resource definitions"""
    ckan_cloud_operator.manager.install_crds()
    great_success()


@main.command()
@click.argument('GITLAB_PROJECT_NAME')
@click.option('-w', '--wait-ready', is_flag=True)
def initialize_gitlab(gitlab_project_name, wait_ready):
    """Initialize the gitlab integration

    Example:

        ckan-cloud-operator initialize-gitlab repo/project
    """
    ckan_gitlab = CkanGitlab(CkanInfra())
    ckan_gitlab.initialize(gitlab_project_name)
    if wait_ready and not ckan_gitlab.is_ready(gitlab_project_name):
        logs.info(f'Waiting for GitLab project {gitlab_project_name} to be ready...')
        while not ckan_gitlab.is_ready(gitlab_project_name):
            time.sleep(5)
    great_success()


@main.command()
def activate_gcloud_auth():
    """Authenticate with gcloud CLI using the ckan-cloud-operator credentials"""
    infra = CkanInfra()
    gcloud_project = infra.GCLOUD_AUTH_PROJECT
    service_account_email = infra.GCLOUD_SERVICE_ACCOUNT_EMAIL
    service_account_json = infra.GCLOUD_SERVICE_ACCOUNT_JSON
    compute_zone = infra.GCLOUD_COMPUTE_ZONE
    if all([gcloud_project, service_account_email, service_account_json]):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(service_account_json.encode())
        try:
            gcloud.check_call(
                f'auth activate-service-account {service_account_email} --key-file={f.name} && '
                f'gcloud --project={gcloud_project} config set compute/zone {compute_zone}',
                with_activate=False,
                ckan_infra=infra
            )
        except Exception:
            traceback.print_exc()
        os.unlink(f.name)
        exit(0)
    else:
        logs.critical('missing gcloud auth details')
        exit(1)


@main.command()
def bash_completion():
    """Return bash completion script which should be eval'd"""
    subprocess.check_call('echo "$(_CKAN_CLOUD_OPERATOR_COMPLETE=source ckan-cloud-operator)"', shell=True)
    print('# ')
    print('# To enable Bash completion, use the following command:')
    print('# eval "$(ckan-cloud-operator bash-completion)"')


@main.command()
@click.argument('MINIO_ROUTER_NAME')
@click.argument('DISK_SIZE_GB')
def initialize_storage(minio_router_name, disk_size_gb):
    """Initialize the centralized storage"""
    # ckan_cloud_operator.storage.deploy_gcs_minio_proxy(gcs_minio_proxy_router_name)
    # ckan_cloud_operator.storage.deploy_storage_permissions_function()
    ckan_cloud_operator.storage.deploy_minio(minio_router_name, disk_size_gb)
    great_success()


@main.command()
def get_storage_credentials():
    print(yaml.dump(kubectl.decode_secret(kubectl.get('secret minio-credentials')), default_flow_style=False))

@main.group()
def users():
    """Manage ckan-cloud-operator users"""
    pass

ckan_cloud_operator.users.add_cli_commands(click, users, great_success)


@main.group()
def ckan_infra():
    """Manage the centralized infrastructure"""
    pass


CkanInfra.add_cli_commands(click, ckan_infra, great_success)


@main.group()
def deis_instance():
    """Manage Deis CKAN instance resources"""
    pass


DeisCkanInstance.add_cli_commands(click, deis_instance, great_success)


@main.group()
def routers():
    """Manage CKAN Cloud routers"""
    pass


ckan_cloud_operator.routers.cli.add_cli_commands(click, routers, great_success)


@main.group()
def datapushers():
    """Manage centralized CKAN DataPushers"""
    pass


ckan_cloud_operator.datapushers.add_cli_commands(click, datapushers, great_success)
