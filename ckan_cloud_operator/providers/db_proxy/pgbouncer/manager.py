import datetime
import time

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers.labels import get_provider_labels, get_provider_label_prefix
from ckan_cloud_operator.providers.db_proxy.constants import PROVIDER_SUBMODULE
from ckan_cloud_operator.providers.db_proxy.pgbouncer.constants import PROVIDER_ID
from ckan_cloud_operator.db import manager as db_manager
from ckan_cloud_operator.providers.service import set_provider
from ckan_cloud_operator.cluster.constants import OPERATOR_NAMESPACE


def initialize():
    _apply_config_secret()
    _apply_service()
    _apply_deployment()


def update(deis_instance_id=None):
    _apply_config_secret(deis_instance_id=deis_instance_id, wait_updated=True)
    for pod_name in kubectl.check_output(
        f'get pods -l app=ckan-cloud-db-proxy-pgbouncer --output=custom-columns=name:.metadata.name --no-headers'
    ).decode().splitlines():
        kubectl.check_call(f'exec {pod_name} -- pgbouncer -q -u pgbouncer -d -R /var/local/pgbouncer/pgbouncer.ini')


def set_as_main_db_proxy():
    set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)


def get_internal_proxy_host_port():
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    return f'{label_prefix}.{OPERATOR_NAMESPACE}', 5432


def _apply_config_secret(deis_instance_id=None, wait_updated=False):
    label_prefix = get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)
    update_dbs = {}
    update_users = {}
    if deis_instance_id:
        user, password, db_name, db_host, db_port = db_manager.get_deis_instance_internal_connection_details(
            deis_instance_id, required=False
        )
        if all([user, password, db_name, db_host, db_port]):
            assert db_name not in update_dbs
            update_dbs[db_name] = f'{db_name} = host={db_host} port={db_port} dbname={db_name}'
            assert user not in update_users
            update_users[user] = password
        user, password, db_name, db_host, db_port = db_manager.get_deis_instance_internal_connection_details(
            deis_instance_id, is_datastore=True, required=False
        )
        if all([user, password, db_name, db_host, db_port]):
            assert db_name not in update_dbs
            update_dbs[db_name] = f'{db_name} = host={db_host} port={db_port} dbname={db_name}'
            assert user not in update_users
            update_users[user] = password
        user, password, db_name, db_host, db_port = db_manager.get_deis_instance_internal_connection_details(
            deis_instance_id, is_datastore=True, is_datastore_readonly=True, required=False
        )
        if all([user, password, db_name, db_host, db_port]):
            assert user not in update_users
            update_users[user] = password
    else:
        dbs, users = db_manager.get_all_dbs_users()
        for db_name, db_host, db_port in dbs:
            assert db_name not in update_dbs
            update_dbs[db_name] = f'{db_name} = host={db_host} port={db_port} dbname={db_name}'
        for name, password in users:
            assert name not in users
            update_users[name] = password
    pg_bouncer_ini = ["[databases]"]
    if deis_instance_id:
        secret = kubectl.decode_secret(kubectl.get(f'secret {label_prefix}-config'))
        for line in secret['pgbouncer.ini'].splitlines():
            if line == '[databases]': continue
            elif line == '': break
            else:
                line_db_name = line.split(' ')[0]
                if line_db_name in update_dbs:
                    update_line = update_dbs.pop(line_db_name)
                    pg_bouncer_ini.append(update_line)
                else:
                    pg_bouncer_ini.append(line)
    for db_name, line in update_dbs.items():
        pg_bouncer_ini.append(line)
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
    if deis_instance_id:
        secret = kubectl.decode_secret(kubectl.get(f'secret {label_prefix}-config'))
        for line in secret['users.txt'].splitlines():
            line_user, line_password = [k.strip('"') for k in line.split(' ')]
            if line_user in update_users:
                password = update_users.pop(line_user)
                users_txt.append(f'"{line_user}" "{password}"')
            else:
                users_txt.append(line)
    for name, password in update_users.items():
        users_txt.append(f'"{name}" "{password}"')
    updated_secret = {
        'pgbouncer.ini': "\n".join(pg_bouncer_ini),
        'users.txt': "\n".join(users_txt)
    }
    kubectl.update_secret(
        f'{label_prefix}-config', updated_secret,
        labels=get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID)
    )
    if wait_updated:
        for retry_num in range(1, 20):
            time.sleep(5)
            if _is_secret_updated(updated_secret): break
            logs.info(f'Waiting for updated pgbouncer secret ({retry_num}/20)..')


def _is_secret_updated(expected_secret):
    expected_hash =  expected_secret['users.txt'] + expected_secret['pgbouncer.ini']
    deployment_app = get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=True)['app']
    has_pod = False
    for pod_name in kubectl.check_output(
        f'get pods -l app={deployment_app} --output=custom-columns=name:.metadata.name --no-headers'
    ).decode().splitlines():
        has_pod = True
        current_hash = kubectl.check_output(f'exec {pod_name} -- bash -c "cat /var/local/pgbouncer/users.txt && cat /var/local/pgbouncer/pgbouncer.ini"').decode()
        if current_hash != expected_hash:
            return False
    return has_pod


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
                                'mountPath': '/var/local/pgbouncer',
                                'readOnly': True
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
