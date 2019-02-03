from ckan_cloud_operator import kubectl

from ckan_cloud_operator.providers.manager import get_provider


def update():
    db_proxy_manager = get_provider('db-proxy', required=False)
    if db_proxy_manager:
        db_proxy_manager.update()


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
    return get_provider('db').get_postgres_admin_credentials()


def get_internal_proxy_host_port():
    db_proxy_manager = get_provider('db-proxy', required=False)
    if db_proxy_manager:
        db_host, db_port = db_proxy_manager.get_internal_proxy_host_port()
    else:
        db_manager = get_provider('db')
        db_host, db_port = db_manager.get_postgres_host_port()
    return db_host, db_port
