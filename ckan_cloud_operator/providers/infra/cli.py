import click

from . import manager

@click.group()
def infra():
    '''
    Manage and debug CKAN related infrastructure like SOLR Cloud and Postgres Databases
    '''
    pass


@click.group('solr')
def infra_solr():
    '''
    Check logs of SolrCloud service and restart them.
    '''
    pass

infra.add_command(infra_solr)


@infra_solr.command('logs')
@click.option('--show-zookeeper', help='Show logs only from zookeper pods', is_flag=True)
@click.option('--since', help='Only return logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs.')
@click.option('--follow', help='Specify if the logs should be streamed.', is_flag=True)
@click.option('--tail', help='Lines of recent log file to display. Defaults to -1 with no selector, showing all log lines otherwise 10, if a selector is provided.')
@click.option('--container', help='Conainer name if multiple')
def infra_solr_logs(**kubectl_args):
    '''
    See logs of SolrCloud and ZooKeeper containers
    '''
    manager.get_container_logs(**kubectl_args)


@infra_solr.command('restart')
@click.option('--zookeper-only', help='Make operations only for zookeper pods', is_flag=True)
@click.option('--solrcloud-only', help='Make operations only for solrcloud pods', is_flag=True)
@click.option('--force', help='Force delete pods', is_flag=True)
def infra_solr_restart(zookeper_only, solrcloud_only, force):
    '''
    Restart SolrCloud and Zookeeper containers
    '''
    manager.restart_solr_pods(zookeper_only, solrcloud_only, force)


@infra_solr.command('list')
@click.option('--format', help='Output Format [default: yaml]', default='wide')
def infra_solr_restart(format):
    '''
    List pods in ckan-cloud namespace
    '''
    manager.get_solr_pods(format)


@click.group('db')
def deployment_db():
    '''
    Manage Database Instance
    '''
    pass

infra.add_command(deployment_db)


@deployment_db.command('get')
def infra_db_get():
    '''
    Get master connection string for ckan Database
    '''
    manager.print_db_connection_string()


@click.argument('INSTANCE_ID')
@click.option('--db', help='Name of database to connect [default: postgres]', default='postgres')
@deployment_db.command('ssh')
def infra_db_ssh(instance_id, db):
    '''
    ssh into Database Instance
    '''
    manager.ssh_into_db(instance_id, db)
