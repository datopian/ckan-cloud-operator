import click
import yaml
import json
import traceback

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

from . import manager


@click.group()
def env():
    '''Manage CKAN Environments
    '''
    pass

@env.command('list')
def list_env():
    '''
    Lists existing environments

    \b
    cco ckan env list
    > POC
    > DEV
    > PRD
    '''

@env.command()
@click.argument('ENVIRONMENT')
@click.option('--cloud-provider', help='One of minukube, azure, gcp, aws', required=True)
@click.option('--cluster-name', help='Kubernetes cluster name', required=True)
@click.option('--resource-group', help='Azure resource group name  [Azure only]')
@click.option('--subscription', help='Azure subscription id  [Azure only]')
@click.option('--region', help='GCP region id Eg: europe-west1  [GCP only]')
@click.option('--project', help='GCP project name  [GCP only]')
def add(environment, cloud_provider, cluster_name, resource_group, subscription, region, project):
    '''
    Adds an environment

    ENVIRONMENT: The name of the environment Eg: poc

    \b
    cco ckan env add poc --cloud-provider cloud-provider-name \\
                         --resource-group resource-group-name \\
                         --cluster-name cluster-name \\
                         --subscription subscription-id \\
                         --region region-name \\
                         --project project-name
    > POC environment was succefully added
    '''

@env.command()
@click.argument('ENVIRONMENT')
@click.option('--cloud-provider', help='One of minukube, azure, gcp, aws')
@click.option('--cluster-name', help='Kubernetes cluster name')
@click.option('--resource-group', help='Azure resource group name  [Azure only]')
@click.option('--subscription', help='Azure subscription id  [Azure only]')
@click.option('--region', help='GCP region id Eg: europe-west1  [GCP only]')
@click.option('--project', help='GCP project name  [GCP only]')
def update(environment, cloud_provider, cluster_name, resource_group, subscription, region, project):
    '''
    Update configurations for given environment

    ENVIRONMENT: The name of the environment Eg: dev

    \b
    cco ckan env add poc --cloud-provider cloud-provider-name \\
                         --resource-group resource-group-name \\
                         --cluster-name new-cluster-name \\
                         --subscription subscription-id \\
                         --region region-name \\
                         --project project-name
    > POC environment was succefully updated
    '''

@env.command()
@click.argument('ENVIRONMENT')
def set(environment):
    '''
    Sets given environment as a current working environment

    ENVIRONMENT: The name of the environment Eg: dev

    \b
    cco ckan env set poc
    > You are working with POC environment now
    '''

@env.command()
@click.argument('ENVIRONMENT')
def rm(environment):
    '''
    Deletes given environment

    ENVIRONMENT: The name of the environment Eg: dev

    cco ckan env rm poc
    > POC environment was succesfully removed
    '''
