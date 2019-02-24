import click

from . import manager


@click.group()
def web_ui():
    """Manage the centralized db web-ui"""
    pass


@web_ui.command()
def initialize():
    manager.initialize()


@web_ui.command()
def start():
    manager.start()
