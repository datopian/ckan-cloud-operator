import click


from .helm import cli as helm_cli


@click.group()
def deployment():
    """Manage App instance deployments"""
    pass


deployment.add_command(helm_cli.helm)
