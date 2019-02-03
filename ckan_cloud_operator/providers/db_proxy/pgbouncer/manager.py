import datetime

from ckan_cloud_operator import kubectl

from ckan_cloud_operator.providers.labels import get_provider_labels, get_provider_label_prefix
from ckan_cloud_operator.providers.db_proxy.constants import PROVIDER_SUBMODULE
from ckan_cloud_operator.providers.db_proxy.pgbouncer.constants import PROVIDER_ID
from ckan_cloud_operator.db import manager as db_manager
from ckan_cloud_operator.providers.service import set_provider
from ckan_cloud_operator.cluster.constants import OPERATOR_NAMESPACE


def initialize():
    update()


def update():
    _apply_config_secret()
    _apply_service()
    _apply_deployment()


def set_as_main_db_proxy():
    set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)


def get_internal_proxy_host_port():
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    return f'{label_prefix}.{OPERATOR_NAMESPACE}', 5432


def _apply_config_secret():
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    dbs, users = db_manager.get_all_dbs_users()
    pg_bouncer_ini = ["[databases]"]
    all_db_names = set()
    for db_name, db_host, db_port in dbs:
        assert db_name not in all_db_names
        pg_bouncer_ini.append(f'{db_name} = host={db_host} port={db_port} dbname={db_name}')
        all_db_names.add(db_name)
    db_admin_user, _, _ = db_manager.get_admin_db_credentials()
    pg_bouncer_ini += [
        "",
        "[pgbouncer]",
        "listen_port = 5432",
        "listen_addr = 0.0.0.0",
        "auth_type = md5",
        "auth_file = /var/local/pgbouncer/users.txt",
        "logfile = /var/log/pgbouncer/pgbouncer.log",
        "pidfile = /var/run/pgbouncer/pgbouncer.pid",
        f"admin_users = {db_admin_user}",
    ]
    users_txt = []
    for name, password in users:
        users_txt.append(f'"{name}" "{password}"')
    pg_bouncer_ini = "\n".join(pg_bouncer_ini)
    users_txt = "\n".join(users_txt)
    kubectl.update_secret(f'{label_prefix}-config', {
        'pgbouncer.ini': pg_bouncer_ini,
        'users.txt': users_txt
    }, labels=get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID))


def _apply_deployment():
    deployment_labels = get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=True)
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    kubectl.apply(kubectl.get_deployment(label_prefix, deployment_labels, {
        'replicas': 2,
        'revisionHistoryLimit': 10,
        'strategy': {'type': 'RollingUpdate', },
        'template': {
            'metadata': {
                'labels': deployment_labels,
                'annotations': {
                    'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                }
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
                                'mountPath': '/var/local/pgbouncer/pgbouncer.ini',
                                'subPath': 'pgbouncer.ini'
                            },
                            {
                                'name': 'config',
                                'mountPath': '/var/local/pgbouncer/users.txt',
                                'subPath': 'users.txt'
                            },
                        ]
                    }
                ],
                'volumes': [
                    {'name': 'config', 'secret': {'secretName': f'{label_prefix}-config'}},
                ]
            }
        }
    }))


def _apply_service():
    deployment_labels = get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=True)
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    kubectl.apply(kubectl.get_service(
        f'{label_prefix}',
        get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID),
        [5432],
        {'app': deployment_labels['app']}
    ))
