import click
import yaml

from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager


@click.group()
def config():
    pass


@config.command()
@click.option('--key')
@click.option('--default')
@click.option('--secret-name')
@click.option('--configmap-name')
@click.option('--namespace')
@click.option('--raw', is_flag=True)
@click.option('--template')
def get(**kwargs):
    """Get configuration values

    Examples:

        - get key foo from default configmap/namespace: get --key foo
        - get key foo from secret in default namespace: get --key foo --secret-name my-secret
        - get all keys from secret in given namespace: get --secret-name my-secret --namespace my-namespace
    """
    raw = kwargs.pop('raw', False)
    data = manager.get(**kwargs)
    if raw or kwargs.get('template'):
        print(data)
    else:
        print(yaml.dump(data, default_flow_style=False))


@config.command()
@click.argument('KEY')
@click.argument('VALUE')
@click.option('--secret-name')
@click.option('--configmap-name')
@click.option('--namespace')
@click.option('--from-file', is_flag=True)
def set(**kwargs):
    """Set a configuration value"""
    manager.set(**kwargs)
    logs.exit_great_success()


@config.command()
@click.argument('KEY')
@click.option('--secret-name')
@click.option('--namespace')
def delete_key(key, secret_name, namespace):
    """Delete a configuration value"""
    manager.delete_key(key, secret_name, namespace)
    logs.exit_great_success()


@config.command()
@click.option('--full', is_flag=True)
@click.option('--show-secrets', is_flag=True)
def list_configs(full, show_secrets):
    for config in manager.list_configs(full=full, show_secrets=show_secrets):
        print(yaml.dump([config], default_flow_style=False))
