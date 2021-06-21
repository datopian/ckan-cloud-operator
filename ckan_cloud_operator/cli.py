import click
import time
import tempfile
import traceback
import os
import subprocess

from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
from ckan_cloud_operator.infra import CkanInfra

import ckan_cloud_operator.routers.cli
import ckan_cloud_operator.datapushers
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator import gcloud
import ckan_cloud_operator.storage
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers import cli as providers_cli
from ckan_cloud_operator.providers.db import cli as db_cli
from ckan_cloud_operator.providers.cluster import cli as cluster_cli
from ckan_cloud_operator.providers.users import cli as users_cli
from ckan_cloud_operator.crds import cli as crds_cli
from ckan_cloud_operator.config import cli as config_cli
from ckan_cloud_operator.drivers.postgres import cli as driver_postgres_cli
from ckan_cloud_operator.providers.ckan import cli as ckan_cli
from ckan_cloud_operator.drivers.kubectl import cli as driver_kubectl_cli
from ckan_cloud_operator.providers.storage import cli as storage_cli
from ckan_cloud_operator.providers.solr import cli as solr_cli
from ckan_cloud_operator.drivers.rancher import cli as driver_rancher_cli
from ckan_cloud_operator.drivers.jenkins import cli as driver_jenkins_cli
from ckan_cloud_operator.drivers.helm import cli as driver_helm_cli
from ckan_cloud_operator.providers.apps import cli as apps_cli


CLICK_CLI_MAX_CONTENT_WIDTH = 200


def great_success(**kwargs):
    logs.info('Great Success!', **kwargs)
    exit(0)


@click.group(context_settings={'max_content_width': CLICK_CLI_MAX_CONTENT_WIDTH})
@click.option('--debug', is_flag=True)
def main(debug):
    """Manage, provision and configure CKAN Clouds and related infrastructure"""
    if debug:
        os.environ.setdefault('CKAN_CLOUD_OPERATOR_DEBUG', 'y')
    pass


main.add_command(ckan_cli.ckan)
main.add_command(cluster_cli.cluster)


############################################################################
## Commands Below are not used for now and are making unnecessary noise   ##
## I'm commenting them for now, but not deleting as they might be useful  ##
## In future. Will bring them back as needed                              ##
############################################################################
#
#
# main.add_command(users_cli.users)
# main.add_command(db_cli.db_group, 'db')
# main.add_command(providers_cli.providers_group, 'providers')
# main.add_command(crds_cli.crds)
# main.add_command(config_cli.config)
# main.add_command(storage_cli.storage)
# main.add_command(solr_cli.solr)
# main.add_command(apps _cli.apps)
#
#
# @main.group()
# def drivers():
#     pass
#
#
# drivers.add_command(driver_postgres_cli.postgres)
# drivers.add_command(driver_kubectl_cli.kubectl)
# drivers.add_command(driver_rancher_cli.rancher)
# drivers.add_command(driver_jenkins_cli.jenkins)
# drivers.add_command(driver_helm_cli.helm)
#
#
# @main.command('kubectl')
# @click.argument('ARG', nargs=-1)
# def kubectl_command(arg):
#     from ckan_cloud_operator import kubectl
#     kubectl.check_call(' '.join(arg))
#
#
# @main.command()
# @click.argument('GITLAB_PROJECT_NAME')
# @click.argument('GIT_BRANCH', default='master')
# @click.option('-w', '--wait-ready', is_flag=True)
# def initialize_gitlab(gitlab_project_name, git_branch, wait_ready):
#     """Initialize the gitlab integration
#
#     Example:
#
#         ckan-cloud-operator initialize-gitlab repo/project
#     """
#     ckan_gitlab = CkanGitlab()
#     ckan_gitlab.initialize(gitlab_project_name, git_branch)
#     if wait_ready and not ckan_gitlab.is_ready(gitlab_project_name):
#         logs.info(f'Waiting for GitLab project {gitlab_project_name} to be ready...')
#         while not ckan_gitlab.is_ready(gitlab_project_name):
#             time.sleep(5)
#     great_success()
#
#
# @main.command()
# def activate_gcloud_auth():
#     """Authenticate with gcloud CLI using the ckan-cloud-operator credentials"""
#     from ckan_cloud_operator.providers.cluster.gcloud import manager as gcloud_manager
#     gcloud_manager.activate_auth()
#
#
# @main.command()
# def bash_completion():
#     """Return bash completion script which should be eval'd"""
#     subprocess.check_call('echo "$(_CKAN_CLOUD_OPERATOR_COMPLETE=source ckan-cloud-operator)"', shell=True)
#     print('# ')
#     print('# To enable Bash completion, use the following command:')
#     print('# eval "$(ckan-cloud-operator bash-completion)"')
#
#
# @main.group()
# def users():
#     """Manage ckan-cloud-operator users"""
#     pass
#
# ckan_cloud_operator.providers.users.add_cli_commands(click, users, great_success)
#
#
# @main.group()
# def ckan_infra():
#     """Manage the centralized infrastructure"""
#     pass
#
#
# CkanInfra.add_cli_commands(click, ckan_infra, great_success)
#
#
# @main.group()
# def deis_instance():
#     """Manage Deis CKAN instance resources"""
#     pass
#
#
# DeisCkanInstance.add_cli_commands(click, deis_instance, great_success)
#
#
# @main.group()
# def routers():
#     """Manage CKAN Cloud routers"""
#     pass
#
#
# ckan_cloud_operator.routers.cli.add_cli_commands(click, routers, great_success)
#
#
# @main.group()
# def datapushers():
#     """Manage centralized CKAN DataPushers"""
#     pass
#
#
# ckan_cloud_operator.datapushers.add_cli_commands(click, datapushers, great_success)
#
#
# @main.command()
# def test():
#     """Run unittest suite and report coverage"""
#     subprocess.check_call('coverage run -m unittest discover', shell=True)
#     subprocess.check_call('coverage report', shell=True)


if __name__ == '__main__':
    main()
