#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from ckan_cloud_operator.providers.db.proxy.pgbouncer.constants import PROVIDER_ID
from ckan_cloud_operator.providers.db.proxy.constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file)
def _config_get_volume_spec(volume_name, is_secret=False, suffix=None): return providers_manager.config_get_volume_spec(PROVIDER_SUBMODULE, PROVIDER_ID, volume_name, is_secret, suffix)

################################
# custom provider code starts here
#

import time
import os
import subprocess
import traceback

from distutils.util import strtobool

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize():
    _apply_config_secret(force=True)
    _apply_service()
    _apply_deployment()
    _set_provider()


def update(wait_updated=False, set_pool_mode=None):
    if set_pool_mode:
        _config_set('pool-mode', set_pool_mode)
    _apply_config_secret()
    if wait_updated:
        logs.info('Waiting 1 minute for pgbouncer secret to be updated...')
        time.sleep(60)
        reload()


def reload():
    deployment_app = _get_resource_labels(for_deployment=True)['app']
    logs.info('Reloading pgbouncers...')
    for pod_name in kubectl.check_output(
            f'get pods -l app={deployment_app} --output=custom-columns=name:.metadata.name --no-headers'
    ).decode().splitlines():
        kubectl.check_call(f'exec {pod_name} -- pgbouncer -q -u pgbouncer -d -R /var/local/pgbouncer/pgbouncer.ini')
        logs.info(f'{pod_name}: PgBouncer Reloaded')


def get_internal_proxy_host_port():
    namespace = cluster_manager.get_operator_namespace_name()
    service_name = _get_resource_name()
    return f'{service_name}.{namespace}', 5432


def get_external_proxy_host_port():
    if strtobool(os.environ.get('CKAN_CLOUD_OPERATOR_USE_PROXY', 'y')):
        host, port = get_external_proxy_forwarded_host_port()
    else:
        host, port = None, None
    return host, port


def get_external_proxy_forwarded_host_port():
    return '127.0.0.1', 5432


def start_port_forward():
    """Starts a local proxy to the cloud SQL instance"""
    print("\nKeep this running in the background\n")
    namespace = cluster_manager.get_operator_namespace_name()
    deployment_name = _get_resource_name()
    subprocess.check_call(f'kubectl -n {namespace} port-forward deployment/{deployment_name} 5432',
                          shell=True)


def _apply_config_secret(force=False):
    update_dbs = {}
    update_users = {}
    try:
        dbs, users = db_manager.get_all_dbs_users()
    except Exception:
        if force:
            traceback.print_exc()
            dbs, users = [], []
        else:
            raise
    for db_name, db_host, db_port in dbs:
        assert db_name not in update_dbs
        update_dbs[db_name] = f'{db_name} = host={db_host} port={db_port} dbname={db_name}'
    for name, password in users:
        assert name not in users
        update_users[name] = password
    pg_bouncer_ini = ["[databases]"]
    for db_name, line in update_dbs.items():
        pg_bouncer_ini.append(line)
    db_admin_user, _, _ = db_manager.get_admin_db_credentials()
    # see https://pgbouncer.github.io/config.html
    pool_mode = _config_get('pool-mode', 'transaction')
    pg_bouncer_ini += [
        "",
        "[pgbouncer]",
        "listen_port = 5432",
        "listen_addr = 0.0.0.0",
        "auth_type = md5",
        "auth_file = /var/local/pgbouncer/users.txt",
        "logfile = /var/log/pgbouncer/pgbouncer.log",
        "pidfile = /var/run/pgbouncer/pgbouncer.pid",
        f"pool_mode = {pool_mode}",
        *([
            "default_pool_size = 8",
            "reserve_pool_size = 8",
            "max_client_conn = 5000",
            "server_round_robin = 1",
            "listen_backlog = 8192",
            "server_idle_timeout = 60",
            "server_lifetime = 600",
        ] if pool_mode == 'transaction' else [
            "default_pool_size = 20",
            "reserve_pool_size = 20",
            "max_client_conn = 5000",
            "server_round_robin = 1",
            "server_fast_close = 1",
            "listen_backlog = 8192",
            "server_lifetime = 5",
        ]),
        f"admin_users = {db_admin_user}",
    ]
    users_txt = []
    for name, password in update_users.items():
        users_txt.append(f'"{name}" "{password}"')
    updated_secret = {
        'pgbouncer.ini': "\n".join(pg_bouncer_ini),
        'users.txt': "\n".join(users_txt)
    }
    _config_set(values=updated_secret, is_secret=True)


def _apply_deployment():
    kubectl.apply(kubectl.get_deployment(
        _get_resource_name(),
        _get_resource_labels(for_deployment=True),
        {
            'replicas': 1,
            'revisionHistoryLimit': 10,
            'strategy': {'type': 'RollingUpdate', },
            'template': {
                'metadata': {
                    'labels': _get_resource_labels(for_deployment=True),
                    'annotations': _get_resource_annotations()
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'pgbouncer',
                            'image': 'viderum/ckan-cloud-operator:pgbouncer',
                            'ports': [{'containerPort': 5432}],
                            'volumeMounts': [
                                {
                                    'name': 'config',
                                    'mountPath': '/var/local/pgbouncer',
                                    'readOnly': True
                                },
                            ],
                            'readinessProbe': {
                                'failureThreshold': 1,
                                'initialDelaySeconds': 5,
                                'periodSeconds': 5,
                                'successThreshold': 1,
                                'tcpSocket': {
                                    'port': 5432
                                },
                                'timeoutSeconds': 5
                            },
                            'resources': {
                                'limits': {
                                    'memory': '2Gi',
                                },
                                'requests': {
                                    'cpu': '0.1',
                                    'memory': '0.2Gi',
                                }
                            }
                        }
                    ],
                    'volumes': [
                        _config_get_volume_spec('config', is_secret=True),
                    ]
                }
            }
        }
    ))


def _apply_service():
    deployment_app = _get_resource_labels(for_deployment=True)['app']
    kubectl.apply(kubectl.get_service(
        _get_resource_name(),
        _get_resource_labels(),
        [5432],
        {'app': deployment_app}
    ))
