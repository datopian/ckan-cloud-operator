import subprocess

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.drivers.postgres import driver as postgres_driver

from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator.providers.db.proxy import manager as db_proxy_manager
from ckan_cloud_operator.providers.ckan import manager as ckan_manager

from .constants import PROVIDER_SUBMODULE as db_provider_submodule
from .gcloudsql.constants import PROVIDER_ID as db_gcloudsql_provider_id


def initialize(log_kwargs=None, interactive=False):
    """Initialize / upgrade the db module and sub-modules"""
    log_kwargs = log_kwargs or {}
    logs.info(f'Initializing DB provider', **log_kwargs)
    db_provider = providers_manager.get_provider(db_provider_submodule, default=db_gcloudsql_provider_id)
    db_provider.initialize(interactive=interactive)
    if db_provider.is_private_ip():
        logs.info('DB Uses a private ip, initializing the DB proxy')
        db_proxy_manager.initialize()


def update():
    db_proxy_manager.update()


def get_all_dbs_users():
    """Get a list of all databases and users, this is used by PgBouncer"""
    all_db_names, all_user_names, duplicate_db_names, duplicate_user_names = {}, {}, set(), set()
    all_dbs = []
    all_users = []
    for dbs_users in [
        _get_admin_dbs_users(),
        ckan_manager.get_all_dbs_users()
    ]:
        dbs, users = dbs_users
        for db in dbs:
            if all([s and s != 'None' for s in db]):
                db_name, _, _ = db
                if db_name in all_db_names:
                    if all_db_names[db_name] != db:
                        duplicate_db_names.add(db_name)
                else:
                    all_dbs.append(db)
                    all_db_names[db_name] = db
        for user in users:
            if all([s and s != 'None' for s in user]):
                user_name, _ = user
                if user_name in all_user_names:
                    if all_user_names[user_name] != user:
                        duplicate_user_names.add(user_name)
                else:
                    all_users.append(user)
                    all_user_names[user_name] = user
    assert len(duplicate_db_names) == 0 and len(duplicate_user_names) == 0, f'Found duplicate db/user names: {duplicate_db_names} / {duplicate_user_names}'
    return all_dbs, all_users


def get_admin_db_credentials():
    db_provider_manager = get_provider()
    admin_user, admin_password, db_name = db_provider_manager.get_postgres_admin_credentials()
    return admin_user, admin_password, db_name


def get_admin_db_user():
    admin_user, admin_password, db_name = get_admin_db_credentials()
    return admin_user


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


def get_external_connection_string(user, password, db_name):
    db_host, db_port = get_external_proxy_host_port()
    return f'postgresql://{user}:{password}@{db_host}:{db_port}/{db_name}'


def get_deis_instance_credentials(instance_id, is_datastore=False, is_datastore_readonly=False, required=True):
    none = None, None, None
    instance_kind = ckan_manager.instance_kind()
    instance = kubectl.get(f'{instance_kind} {instance_id}', required=required)
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
    """Returns connection details for internal cluster access, via proxy if enabled"""
    db_proxy_provider = db_proxy_manager.get_provider(required=False)
    if db_proxy_provider:
        db_host, db_port = db_proxy_provider.get_internal_proxy_host_port()
    else:
        db_provider_manager = get_provider()
        db_host, db_port = db_provider_manager.get_postgres_internal_host_port()
    return db_host, db_port


def get_external_proxy_host_port():
    """Returns connection details for access from outside the cluster, via proxy if enabled"""
    db_proxy_provider = db_proxy_manager.get_provider(required=False)
    if db_proxy_provider:
        host, port = db_proxy_provider.get_external_proxy_host_port()
        if host and port:
            return host, port
    return get_provider().get_postgres_external_host_port()


def get_internal_unproxied_db_host_port():
    db_provider_manager = get_provider()
    return db_provider_manager.get_postgres_internal_host_port()


def get_provider():
    return providers_manager.get_provider(db_provider_submodule)


def check_db_exists(db_name):
    admin_connection_string = get_external_admin_connection_string()
    with postgres_driver.connect(admin_connection_string) as admin_conn:
        return len(list(postgres_driver.list_roles(admin_conn, role_name=db_name))) > 0


def check_connection_string(connection_string):
    with postgres_driver.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute('select 1')


def _get_admin_dbs_users():
    db_provider_manager = get_provider()
    db_host, db_port = db_provider_manager.get_postgres_internal_host_port()
    db_admin_user, db_admin_password, db_admin_db = db_provider_manager.get_postgres_admin_credentials()
    dbs = [(db_admin_db, db_host, db_port)]
    users = [(db_admin_user, db_admin_password)]
    return dbs, users
