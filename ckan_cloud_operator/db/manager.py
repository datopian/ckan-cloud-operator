import os
import subprocess

from ckan_cloud_operator import kubectl

from ckan_cloud_operator.providers.manager import get_provider
from ckan_cloud_operator.providers.service import set_provider
from ckan_cloud_operator.providers.db_web_ui.constants import PROVIDER_SUBMODULE as db_web_ui_submodule
from ckan_cloud_operator.providers.db_web_ui.adminer.constants import PROVIDER_ID as adminer_provider_id
from ckan_cloud_operator.infra import CkanInfra


def update(deis_instance_id=None):
    db_proxy_manager = get_provider('db-proxy', required=False)
    if db_proxy_manager:
        db_proxy_manager.update(deis_instance_id=deis_instance_id)


def get_all_dbs_users():
    db_manager = get_provider('db')
    db_host, db_port = db_manager.get_postgres_host_port()
    db_admin_user, db_admin_password, db_admin_db = db_manager.get_postgres_admin_credentials()
    users, dbs = [(db_admin_user, db_admin_password)], [(db_admin_db, db_host, db_port)]
    for instance in kubectl.get(f'DeisCkanInstance')['items']:
        instance_id = instance['metadata']['name']
        db_name = instance['spec']['db']['name']
        datastore_name = instance['spec']['datastore']['name']
        secret = kubectl.decode_secret(kubectl.get(
            f'secret {instance_id}-annotations', namespace=instance_id,
            required=False
        ), required=False)
        if db_name:
            dbs.append((db_name, db_host, db_port))
            if secret.get('databasePassword'):
                users.append((db_name, secret['databasePassword']))
        if datastore_name:
            dbs.append((datastore_name, db_host, db_port))
            if secret.get('datastorePassword'):
                users.append((datastore_name, secret['datastorePassword']))
            if secret.get('datatastoreReadonlyPassword') and secret.get('datastoreReadonlyUser'):
                users.append((secret['datastoreReadonlyUser'], secret['datatastoreReadonlyPassword']))
    return dbs, users


def get_admin_db_credentials():
    admin_user, admin_password, db_name = get_provider('db').get_postgres_admin_credentials()
    return admin_user, admin_password, db_name


def get_external_admin_connection_string(db_name=None):
    """Get an admin connection string for access from outside the cluster"""
    admin_user, admin_password, admin_db_name = get_admin_db_credentials()
    if not db_name:
        db_name = admin_db_name
    db_host, db_port = get_external_proxy_host_port()
    return f'postgresql://{admin_user}:{admin_password}@{db_host}:{db_port}/{db_name}'


def get_deis_instsance_external_connection_string(instance_id, is_datastore=False, is_datastore_readonly=False):
    user, password, db_name, db_host, db_port = get_deis_instance_external_connection_details(
        instance_id, is_datastore=is_datastore, is_datastore_readonly=is_datastore_readonly
    )
    return f'postgresql://{user}:{password}@{db_host}:{db_port}/{db_name}'


def get_deis_instance_credentials(instance_id, is_datastore=False, is_datastore_readonly=False, required=True):
    none = None, None, None
    instance = kubectl.get(f'DeisCkanInstance {instance_id}', required=required)
    if not instance: return none
    secret = kubectl.get(f'secret {instance_id}-annotations', namespace=instance_id, required=required)
    if not secret: return none
    secret = kubectl.decode_secret(secret)
    if is_datastore or is_datastore_readonly:
        db_name = user = instance['spec'].get('datastore', {}).get('name')
        if is_datastore_readonly:
            user = secret.get('datastoreReadonlyUser')
            password = secret.get('datatastoreReadonlyPassword')
        else:
            password = secret.get('datastorePassword')
    else:
        db_name = user = instance['spec'].get('db', {}).get('name')
        password = secret.get('databasePassword')
    res = [user, password, db_name]
    if all(res):
        return res
    else:
        assert not required, 'missing some db values'
        return none


def get_deis_instance_internal_connection_details(instance_id, is_datastore=False, is_datastore_readonly=False, required=True):
    user, password, db_name = get_deis_instance_credentials(instance_id, is_datastore, is_datastore_readonly, required)
    db_host, db_port = get_internal_proxy_host_port()
    res = [user, password, db_name, db_host, db_port]
    if all(res):
        return res
    else:
        assert not required, 'missing some db values'
        return None, None, None, None, None


def get_deis_instance_external_connection_details(instance_id, is_datastore=False, is_datastore_readonly=False, required=True):
    user, password, db_name = get_deis_instance_credentials(instance_id, is_datastore, is_datastore_readonly, required)
    db_host, db_port = get_external_proxy_host_port()
    res = [user, password, db_name, db_host, db_port]
    if all(res):
        return res
    else:
        assert not required, 'missing some db values'
        return None, None, None, None, None


def get_internal_proxy_host_port():
    """Returns connection details for internal cluster access"""
    db_proxy_manager = get_provider('db-proxy', required=False)
    if db_proxy_manager:
        db_host, db_port = db_proxy_manager.get_internal_proxy_host_port()
    else:
        db_manager = get_provider('db')
        db_host, db_port = db_manager.get_postgres_host_port()
    return db_host, db_port


def get_external_proxy_host_port():
    """Returns connection details for access from outside the cluster"""
    if os.environ.get('CKAN_CLOUD_OPERATOR_USE_PROXY') in ['yes', '1', 'true']:
        return '127.0.0.1', 5432
    else:
        raise Exception('direct access to the DB is not supported from external operators')


def web_ui():
    print('\n')
    print('Starting DB web-ui')
    print('\n')
    admin_user, admin_password, db_name = get_admin_db_credentials()
    db_manager = get_provider('db')
    db_host, db_port = db_manager.get_postgres_host_port()
    print(f'admin db name: {db_name}')
    print('\n')
    print(f'{admin_user} password: {admin_password}')
    url = f'http://localhost:8080/?pgsql={db_host}&username={admin_user}'
    print('\n')
    print(f'Use the following url to open adminer: {url}')
    print('\n')
    get_provider(db_web_ui_submodule).web_ui()


def initialize_web_ui():
    set_provider(db_web_ui_submodule, adminer_provider_id)
    get_provider(db_web_ui_submodule).initialize()


def check_db_exists(db_name):
    admin_db_connection_string = get_external_admin_connection_string()
    cmd = f"psql -d {admin_db_connection_string} -c \"select 1 from pg_database where datname='{db_name}';\" -t"
    return subprocess.check_output(cmd, shell=True).decode().strip() == '1'
