import click
import yaml

from . import driver


@click.group()
def kubectl():
    """Manage Kubernetes resources unrelated to the operator or cluster"""
    pass


@kubectl.command()
@click.argument('WHAT')
@click.argument('ARGS', nargs=-1)
@click.option('--required', is_flag=True)
@click.option('--namespace')
@click.option('--get-cmd', default='get')
@click.option('--default-flow-style', is_flag=True)
def get(what, args, required, namespace, get_cmd, default_flow_style):
    if not namespace: namespace = 'ckan-cloud'
    print(yaml.dump(
        driver.get(what, *args, required=required, namespace=namespace, get_cmd=get_cmd),
        default_flow_style=default_flow_style
    ))
