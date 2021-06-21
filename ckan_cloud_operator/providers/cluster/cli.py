import click
import time

from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.cluster import manager
from ckan_cloud_operator.labels import manager as labels_manager

from .aws.cli import aws as aws_cli


@click.group()
def cluster():
    """Manage the cluster"""
    pass


@cluster.command()
@click.option('--interactive', is_flag=True)
@click.option('--cluster-provider', default='gcloud')
@click.option('--skip-to')
def initialize(interactive, cluster_provider, skip_to):
    """Initialize the currently connected cluster"""
    manager.initialize(interactive=interactive, default_cluster_provider=cluster_provider, skip_to=skip_to)
    logs.exit_great_success()



############################################################################
## Commands Below are not used for now and are making unnecessary noise   ##
## I'm commenting them for now, but not deleting as they might be useful  ##
## In future. Will bring them back as needed                              ##
############################################################################


# cluster.add_command(aws_cli)
#
# @cluster.command()
# @click.option('--debug', is_flag=True)
# @click.option('--full', is_flag=True)
# def info(debug, full):
#     manager.print_info(debug=debug, minimal=not full)
#
#
# @cluster.command()
# @click.argument('DISK_SIZE_GB')
# @click.argument('ZONE', required=False, default=0)
# def create_volume(disk_size_gb, zone):
#     label_prefix = labels_manager.get_label_prefix()
#     print(manager.create_volume(
#         disk_size_gb,
#         {f'{label_prefix}/operator-volume-source': 'cli'},
#         zone=zone
#     ))
#
#
# @cluster.command()
# @click.argument('COMMAND', nargs=-1)
# def provider_exec(command):
#     manager.provider_exec(' '.join(command))
#
#
# @cluster.command()
# @click.option('--expander', default='random', help='random|most-pods|least-waste|price (default: random)')
# @click.option('--min-nodes', type=int, help='specifies the minimum number of nodes for the node pool [gcloud provider only]')
# @click.option('--max-nodes', type=int, help='specifies the maximum number of nodes for the node pool [gcloud provider only]')
# @click.option('--zone', help='specifies the cluster\'s compute zone [gcloud provider only]')
# @click.option('--node-pool', help='specifies the desired node pool. If you have only one node pool, supply default-pool to this flag. [gcloud provider only]')
# def setup_autoscaler(expander, min_nodes, max_nodes, zone, node_pool):
#     """Set up the cluster autoscaler from stable/cluster-autoscaler helm package"""
#     manager.setup_autoscaler(expander, min_nodes, max_nodes, zone, node_pool)
