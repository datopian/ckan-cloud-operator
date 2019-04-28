import click
import yaml

from . import driver
from ckan_cloud_operator import logs


@click.group()
def jenkins():
    """Interact with a Jenkins server"""
    pass


@jenkins.command()
@click.argument('JENKINS_USER')
@click.argument('JENKINS_TOKEN')
@click.argument('JENKINS_URL')
@click.argument('POST_JSON_DATA', required=False)
def curl(jenkins_user, jenkins_token, jenkins_url, post_json_data):
    logs.print_yaml_dump(driver.curl(jenkins_user, jenkins_token, jenkins_url, post_json_data))
    logs.exit_great_success(quiet=True)
