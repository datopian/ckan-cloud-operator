import click
import binascii
import os
import yaml

from ckan_cloud_operator import logs

from . import driver


_api_endpoint, _access_key, _secret = None, None, None


def _driver_yaml_dump(method, *args, **kwargs):
    print(yaml.dump(getattr(driver, method)(_api_endpoint, _access_key, _secret, *args, **kwargs),
                    default_flow_style=False))


@click.group()
@click.option('--api-endpoint')
@click.option('--access-key')
@click.option('--secret')
def rancher(api_endpoint, access_key, secret):
    """Manage Rancher unrelated to the operator or cluster"""
    global _api_endpoint, _access_key, _secret
    _api_endpoint, _access_key, _secret = api_endpoint, access_key, secret


@rancher.command()
@click.argument('USERNAME')
@click.argument('PASSWORD')
def create_user(username, password):
    print(yaml.dump(driver.create_user(_api_endpoint, _access_key, _secret, username, password), default_flow_style=False))
    logs.exit_great_success(quiet=True)


@rancher.command()
@click.argument('CLUSTER_ID')
@click.argument('USER_ID')
@click.argument('USER_PRINCIPAL_ID')
def create_admin_role_bindings(cluster_id, user_id, user_principal_id):
    _driver_yaml_dump('create_cluster_role_template_binding', cluster_id, user_principal_id)
    print('---')
    _driver_yaml_dump('create_global_role_binding', user_id)
    logs.exit_great_success(quiet=True)


@rancher.command()
@click.argument('USERNAME')
@click.argument('PASSWORD')
def login(username, password):
    print(yaml.dump(driver.login(_api_endpoint, username, password), default_flow_style=False))
    logs.exit_great_success(quiet=True)


@rancher.command()
@click.argument('USER_LOGIN_TOKEN')
@click.argument('TOKEN_DESCRIPTION')
def create_user_token(user_login_token, token_description):
    print(yaml.dump(driver.create_user_token(_api_endpoint, user_login_token, token_description), default_flow_style=False))
    logs.exit_great_success(quiet=True)
