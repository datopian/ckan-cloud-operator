import binascii
import os
import datetime
import traceback
import time

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

from ckan_cloud_operator.drivers.postgres import driver as postgres_driver

from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.db.proxy import manager as db_proxy_manager
from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager

from ckan_cloud_operator.infra import CkanInfra

from ckan_cloud_operator.providers.cluster.constants import PROVIDER_SUBMODULE as cluster_provider_submodule
from ckan_cloud_operator.providers.db.constants import PROVIDER_SUBMODULE as db_provider_submodule

from .constants import PROVIDER_SUBMODULE

from .constants import (
    MIGRATION_CRD_KIND as CRD_KIND,
    MIGRATION_CRD_PLURAL as CRD_PLURAL,
    MIGRATION_CRD_SINGULAR as CRD_SINGULAR,
    MIGRATION_EVENT_STATUS_SUCCESS as STATUS_SUCCESS,
    MIGRATION_EVENT_STATUS_FAILURE as STATUS_FAILURE
)


def initialize(log_kwargs=None, interactive=False):
    log_kwargs = log_kwargs or {}
    logs.info(f'Installing crds', **log_kwargs)
    crds_manager.install_crd(CRD_SINGULAR, CRD_PLURAL, CRD_KIND, hash_names=True)
    if cluster_manager.get_provider_id() == 'gcloud':
        ckan_infra = CkanInfra(required=False)
        if interactive:
            providers_manager.config_interactive_set(
                PROVIDER_SUBMODULE,
                default_values={'gcloud-storage-import-bucket': ckan_infra.GCLOUD_SQL_DEIS_IMPORT_BUCKET},
                suffix='deis-migration'
            )
        else:
            if not providers_manager.config_get(PROVIDER_SUBMODULE, key='gcloud-storage-import-bucket', suffix='deis-migration', required=False):
                providers_manager.config_set(
                    PROVIDER_SUBMODULE,
                    values={'gcloud-storage-import-bucket': ckan_infra.GCLOUD_SQL_DEIS_IMPORT_BUCKET},
                    suffix='deis-migration'
                )


def get(name=None, required=True):
    return crds_manager.get(CRD_SINGULAR, name=name, required=required)


def create(name, spec, force=False, exists_ok=False, delete_dbs=False):
    migration = get(name, required=False)
    if migration:
        if force or delete_dbs:
            delete(name, delete_dbs=delete_dbs)
        elif exists_ok:
            return migration
        else:
            logs.error('migration name conflict: ' + str(migration.get('spec')))
            raise Exception(f'migration already exists: {name}, Run with --force / --rerun / --recreate-dbs')
    logs.info(f'Creating migration name {name} (spec={spec})')
    migration = crds_manager.get_resource(
        CRD_SINGULAR,
        name,
        spec=_get_spec(name, spec),
        extra_label_suffixes=_get_labels(name, spec)
    )
    kubectl.apply(migration)
    return migration


def delete(name, delete_dbs=False):
    migration = crds_manager.get(CRD_SINGULAR, name=name, required=False) or {}
    if delete_dbs:
        db_prefix = migration.get('spec', {}).get('db-prefix') or ''
        admin_connection_string = db_manager.get_external_admin_connection_string(db_prefix=db_prefix)
        db_name = migration.get('spec', {}).get('datastore-name')
        datastore_name = migration.get('spec', {}).get('db-name')
        datastore_ro_name = crds_manager.config_get(CRD_SINGULAR, name, key='datastore-readonly-user-name', is_secret=True, required=False)
        if db_name or datastore_name or datastore_ro_name:
            with postgres_driver.connect(admin_connection_string) as admin_conn:
                _delete_dbs(admin_conn, db_name, datastore_name, datastore_ro_name)
    crds_manager.delete(CRD_SINGULAR, name)


def migrate_deis_dbs(old_site_id=None, db_name=None, datastore_name=None, force=False, rerun=False, recreate_dbs=False,
                     dbs_suffix=None, skip_create_dbs=False, skip_datastore_import=False,
                     db_import_url=None, datastore_import_url=None, db_prefix=None):
    if not dbs_suffix: dbs_suffix = ''
    if not db_prefix: db_prefix = db_manager.get_default_db_prefix()
    if db_import_url or datastore_import_url:
        assert db_import_url and datastore_import_url
        assert db_name and datastore_name
        assert not old_site_id
        logs.info(f'Restoring from backup: {db_import_url}, {datastore_import_url} -> {db_name}, {datastore_name} ({db_prefix})')
        assert not skip_datastore_import
        migration_name = f'restore-{db_name}-{datastore_name}'
        if len(migration_name) > 50:
            migration_name = f'rr-{db_name}'
        if db_prefix:
            migration_name += f'-{db_prefix}'
    else:
        assert old_site_id
        assert not db_import_url and not datastore_import_url
        if not db_name: db_name = f'{old_site_id}{dbs_suffix}'
        if not datastore_name: datastore_name = f'{db_name}{dbs_suffix}-datastore'
        logs.info(f'Starting migration ({old_site_id} -> {db_name}, {datastore_name})')
        if skip_datastore_import:
            logs.warning('skipping datastore DB import')
        migration_name = f'deis-dbs-{old_site_id}-to-{db_name}--{datastore_name}'
        if len(migration_name) > 50:
            migration_name = f'dd-{old_site_id}-{db_name}'
        if db_prefix:
            migration_name += f'-{db_prefix}'
    migration = create(
        name=migration_name,
        spec={
            'type': 'deis-ckan',
            'old-site-id': old_site_id,
            'db-name': db_name,
            'datastore-name': datastore_name,
            'skip-datastore-import': skip_datastore_import,
            'db-import-url': db_import_url,
            'datastore-import-url': datastore_import_url,
            'db-prefix': db_prefix
        },
        force=force,
        exists_ok=rerun and not force,
        delete_dbs=recreate_dbs
    )
    yield {'step': 'created-migration-resource',
           'msg': f'Created the migration custom resource: {migration_name}',
           'migration-name': migration_name}
    yield from update(migration, recreate_dbs=recreate_dbs, skip_create_dbs=skip_create_dbs)
    yield {'step': 'migration-complete', 'msg': f'Migration completed successfully for: {migration_name}', 'status': STATUS_SUCCESS}


def update(migration, recreate_dbs=False, skip_create_dbs=False):
    migration_type = migration['spec']['type']
    if migration_type == 'deis-ckan':
        if migration['spec'].get('imported-data'):
            yield {'step': 'imported-data', 'msg': 'data already imported'}
        else:
            migration_name = migration['spec']['name']
            db_name = migration['spec']['db-name']
            datastore_name = migration['spec']['datastore-name']
            datastore_ro_name = _get_or_create_datastore_readonly_user_name(migration_name, datastore_name)
            db_prefix = migration['spec'].get('db-prefix')
            if not skip_create_dbs:
                yield from _create_base_dbs_and_roles(migration_name, db_name, datastore_name, recreate_dbs, datastore_ro_name,
                                                      db_prefix=db_prefix)
                yield from _initialize_postgis_extensions(db_name, db_prefix)
            yield from _import_data(migration['spec']['old-site-id'], db_name, datastore_name,
                                    skip_datastore_import=migration['spec'].get('skip-datastore-import'),
                                    db_import_url=migration['spec'].get('db-import-url'),
                                    datastore_import_url=migration['spec'].get('datastore-import-url'),
                                    db_prefix=db_prefix)
            migration['spec']['imported-data'] = True
            kubectl.apply(migration)
    elif migration_type == 'new-db':
        if migration['spec'].get('created-db'):
            yield {'step': 'created-db', 'msg': 'DB Already created'}
        else:
            migration_name = migration['spec']['name']
            db_name = migration['spec']['db-name']
            db_prefix = migration['spec'].get('db-prefix')
            yield from _create_base_dbs_and_roles(migration_name, db_name, None, recreate_dbs, None, db_prefix=db_prefix)
            yield from _initialize_postgis_extensions(db_name, db_prefix)
            migration['spec']['created-db'] = True
            kubectl.apply(migration)
    elif migration_type == 'new-datastore':
        if migration['spec'].get('created-datastore'):
            yield {'step': 'created-datastore', 'msg': 'Datastore Already created'}
        else:
            migration_name = migration['spec']['name']
            datastore_name = migration['spec']['datastore-name']
            datastore_ro_name = _get_or_create_datastore_readonly_user_name(migration_name, datastore_name)
            db_prefix = migration['spec'].get('db-prefix')
            yield from _create_base_dbs_and_roles(migration_name, None, datastore_name, recreate_dbs, datastore_ro_name, db_prefix=db_prefix)
            migration['spec']['created-datastore'] = True
            kubectl.apply(migration)
    else:
        raise Exception(f'Unknown migration type: {migration_type}')


def get_all_dbs_users():
    dbs, users = [], []
    for migration in crds_manager.get(CRD_SINGULAR)['items']:
        migration_name = migration['spec']['name']
        spec = migration['spec']
        if spec.get('type') == 'deis-ckan':
            db_name = spec['db-name']
            datastore_ro_name = get_datastore_raedonly_user_name(migration_name, required=False)
            datastore_name = spec['datastore-name']
            db_password, datastore_password, datastore_ro_password = get_dbs_passwords(migration_name, required=False)
            if all([db_password, datastore_password, datastore_ro_password, db_name, datastore_name, datastore_ro_name]):
                db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
                dbs.append((db_name, db_host, db_port))
                dbs.append((datastore_name, db_host, db_port))
                users.append((db_name, db_password))
                users.append((datastore_name, datastore_password))
                users.append((datastore_ro_name, datastore_ro_password))
        elif spec.get('type') == 'new-db':
            db_name = spec['db-name']
            db_password, _, _ = get_dbs_passwords(migration_name, required=False)
            if db_password:
                db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
                dbs.append((db_name, db_host, db_port))
                users.append((db_name, db_password))
        elif spec.get('type') == 'new-datastore':
            datastore_ro_name = get_datastore_raedonly_user_name(migration_name, required=False)
            datastore_name = spec['datastore-name']
            _, datastore_password, datastore_ro_password = get_dbs_passwords(migration_name, required=False)
            if datastore_password and datastore_ro_password:
                db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
                dbs.append((datastore_name, db_host, db_port))
                users.append((datastore_name, datastore_password))
                users.append((datastore_ro_name, datastore_ro_password))
    return dbs, users


def print_event_exit_on_complete(event, details_msg, soft_exit=False):
    if not details_msg: details_msg = ''
    msg = event.pop('msg')
    step = event.pop('step')
    logs.info(f'{step}: {msg}')
    if len(event)> 0:
        logs.info(f'event metadata: {event}')
    event_completed_successfully = get_event_migration_complete_status(event)
    if event_completed_successfully:
        logs.info(f'Migration completed successfully ({details_msg})')
        if soft_exit:
            return True
        else:
            logs.exit_great_success()
    elif event_completed_successfully is False:
        logs.error(f'Migration failed ({details_msg})')
        if soft_exit:
            return False
        else:
            logs.exit_catastrophic_failure()
    else:
        return None


def get_event_migration_complete_status(event):
    status = event.get('status')
    if not status: return None
    return {
        STATUS_SUCCESS: True,
        STATUS_FAILURE: False,
    }.get(status, None)


def get_event_migration_created_name(event):
    if event.get('step') == 'created-migration-resource':
        return event['migration-name']
    else:
        return None


def get_dbs_passwords(migration_name, required=False):
    database_password, datastore_password, datastore_readonly_password = [
        crds_manager.config_get(
            CRD_SINGULAR, migration_name, key=key, is_secret=True, required=required
        )
        for key in ['database-password', 'datastore-password', 'datastore-readonly-password']
    ]
    return database_password, datastore_password, datastore_readonly_password


def get_datastore_raedonly_user_name(migration_name, required=False):
    return crds_manager.config_get(CRD_SINGULAR, migration_name,
                                   key='datastore-readonly-user-name', is_secret=True, required=required)


def get_db_import_urls(old_site_id):
    import_backup = providers_manager.config_get(PROVIDER_SUBMODULE, key='gcloud-storage-import-bucket', suffix='deis-migration', required=True)
    instance_latest_datestring = None
    instance_latest_dt = None
    instance_latest_datastore_datestring = None
    instance_latest_datastore_dt = None
    for line in _gcloud().check_output(f"ls 'gs://{import_backup}/postgres/????????/*.sql'",
                                       gsutil=True).decode().splitlines():
        # gs://viderum-deis-backups/postgres/20190122/nav.20190122.dump.sql
        datestring, filename = line.split('/')[4:]
        file_instance = '.'.join(filename.split('.')[:-3])
        is_datastore = file_instance.endswith('-datastore')
        file_instance = file_instance.replace('-datastore', '')
        dt = datetime.datetime.strptime(datestring, '%Y%m%d')
        if file_instance == old_site_id:
            if is_datastore:
                if instance_latest_datastore_dt is None or instance_latest_datastore_dt < dt:
                    instance_latest_datastore_datestring = datestring
                    instance_latest_datastore_dt = dt
            elif instance_latest_dt is None or instance_latest_dt < dt:
                instance_latest_datestring = datestring
                instance_latest_dt = dt
    return (
        f'gs://{import_backup}/postgres/{instance_latest_datestring}/{old_site_id}.{instance_latest_datestring}.dump.sql' if instance_latest_datestring else None,
        f'gs://{import_backup}/postgres/{instance_latest_datastore_datestring}/{old_site_id}-datastore.{instance_latest_datastore_datestring}.dump.sql' if instance_latest_datastore_datestring else None
    )


def _get_spec(name, spec):
    return dict(name=name, **spec)


def _get_labels(name, spec):
    labels = {'name': name}
    if 'old-site-id' in spec:
        labels['old-site-id'] = spec['old-site-id']
    return labels


def _get_or_create_migration_db_passwords(migration_name, create_if_not_exists=True, skip_keys=None):
    passwords = []
    errors = []
    for password_config_key in ['database-password', 'datastore-password', 'datastore-readonly-password']:
        if skip_keys is not None and password_config_key not in skip_keys:
            passwords.append(None)
            continue
        password = crds_manager.config_get(
            CRD_SINGULAR, migration_name, key=password_config_key, is_secret=True, required=False
        )
        if create_if_not_exists:
            if password:
                logs.info(f'Password already exists: {password_config_key}')
                errors.append(f'password-exists: {password_config_key}')
            else:
                logs.info(f'Generating new password for {password_config_key}')
                password = _generate_password()
                crds_manager.config_set(
                    CRD_SINGULAR, migration_name,
                    key=password_config_key, value=password,
                    is_secret=True
                )
        passwords.append(password)
    return [errors] + passwords


def _generate_password():
    return binascii.hexlify(os.urandom(12)).decode()


def _get_or_create_datastore_readonly_user_name(migration_name, datastore_name):
    name = crds_manager.config_get(CRD_SINGULAR, migration_name,
                                   key='datastore-readonly-user-name', is_secret=True, required=False)
    if not name:
        name = f'{datastore_name}-ro'
        crds_manager.config_set(CRD_SINGULAR, migration_name,
                                key='datastore-readonly-user-name', value=name, is_secret=True)
    return name


def _initialize_postgis_extensions(db_name, db_prefix):
    logs.info('initializing postgis extensions for main db')
    connection_string = db_manager.get_external_admin_connection_string(db_name, db_prefix=db_prefix)
    with postgres_driver.connect(connection_string) as conn:
        postgres_driver.initialize_extensions(conn, [
            'postgis', 'postgis_topology', 'fuzzystrmatch', 'postgis_tiger_geocoder'
        ])
        with conn.cursor() as cur:
            try:
                cur.execute(f'ALTER TABLE spatial_ref_sys OWNER TO "{db_name}"')
            except Exception:
                traceback.print_exc()
    yield {'step': 'initialize-postgis', 'msg': f'Initialized postgis for db: {db_name} ({db_prefix})'}


def _update_db_proxy(db_name, datastore_name, datastore_ro_name, db_password, datastore_password, datastore_ro_password, db_prefix):
    logs.info('Updating db proxy')
    db_proxy_manager.update(wait_updated=False)
    ok = False
    for i in range(5):
        try:
            for user, password, db in [(db_name, db_password, db_name),
                                       (datastore_name, datastore_password, datastore_name),
                                       (datastore_ro_name, datastore_ro_password, datastore_name)]:
                if user:
                    db_manager.check_connection_string(
                        db_manager.get_external_connection_string(user, password, db, db_prefix=db_prefix)
                    )
            ok = True
            break
        except Exception as e:
            logs.warning(str(e))
        logs.info(f'Waiting for connection to db proxy...')
        # 40 seconds on first iteration - to ensure secret is updated in pgbouncer volume
        time.sleep(40 if i == 0 else 1)
        db_proxy_manager.reload()
        time.sleep(10 if i == 2 else 5)
    assert ok, 'failed to get connection to db proxy'
    yield {'step': 'update-db-proxy',
           'msg': f'Updated DB Proxy with the new dbs and roles: {db_name}, {datastore_name}, {datastore_ro_name} ({db_prefix})'}


def _create_base_dbs_and_roles(migration_name, db_name, datastore_name, recreate_dbs, datastore_ro_name, db_prefix=None):
    logs.info('Creating base DBS')
    admin_connection_string = db_manager.get_external_admin_connection_string(db_prefix=db_prefix)
    with postgres_driver.connect(admin_connection_string) as admin_conn:
        if recreate_dbs:
            _delete_dbs(admin_conn, db_name, datastore_name, datastore_ro_name)
        if not datastore_name:
            skip_keys = ['database-password']
        elif not db_name:
            skip_keys = ['datastore-password', 'datastore-readonly-password']
        else:
            skip_keys = None
        password_errors, db_password, datastore_password, datastore_ro_password = _get_or_create_migration_db_passwords(
            migration_name,
            skip_keys=skip_keys
        )
        yield {'step': 'get-create-passwords', 'msg': 'Created Passwords'}
        admin_user = db_manager.get_admin_db_user(db_prefix=db_prefix)
        if db_name:
            db_errors = postgres_driver.create_base_db(admin_conn, db_name, db_password, grant_to_user=admin_user)
        else:
            db_errors = []
        if datastore_name:
            datastore_errors = postgres_driver.create_base_db(admin_conn, datastore_name, datastore_password,
                                                              grant_to_user=admin_user)
        else:
            datastore_errors = []
        if datastore_name and db_name:
            assert (len(datastore_errors) == 0 and len(db_errors) == 0) or len(password_errors) == 3, \
                'some passwords were not created, but DB / roles need to be created, we cannot know the right passwords'
        yield {'step': 'create-base-dbs', 'msg': f'Created Base DB and roles: {db_name}, {datastore_name} ({db_prefix})'}
        if datastore_name:
            postgres_driver.create_role_if_not_exists(admin_conn, datastore_ro_name, datastore_ro_password)
            yield {'step': 'created-datastore-ro-role', 'msg': f'Created Datastore read-only user: {datastore_ro_name} ({db_prefix})'}
    yield {'step': 'created-base-dbs-and-roles', f'msg': f'Created base dbs and roles: {db_name}, {datastore_name}, {datastore_ro_name} ({db_prefix})'}
    yield from _update_db_proxy(db_name, datastore_name, datastore_ro_name, db_password, datastore_password, datastore_ro_password, db_prefix)


def _delete_dbs(admin_conn, db_name, datastore_name, datastore_ro_name):
    if db_name:
        postgres_driver.delete_base_db(admin_conn, db_name)
    if datastore_name:
        postgres_driver.delete_base_db(admin_conn, datastore_name)
    if datastore_ro_name:
        postgres_driver.delete_role(admin_conn, datastore_ro_name)


def _import_data(old_site_id, db_name, datastore_name, skip_datastore_import=False,
                 db_import_url=None, datastore_import_url=None,
                 import_user=None, db_prefix=None):
    if db_import_url or datastore_import_url:
        assert db_import_url and datastore_import_url
        db_url, datastore_url = db_import_url, datastore_import_url
    else:
        db_url, datastore_url = get_db_import_urls(old_site_id)
    assert db_url and (datastore_url or skip_datastore_import), f'failed to find db import urls for old site id {old_site_id}'
    _gcloudsql().import_db(db_url, db_name, import_user=import_user or db_name, db_prefix=db_prefix)
    yield {'step': 'import-db-data', 'msg': f'Imported DB: {db_name}'}
    if skip_datastore_import:
        yield {'step': 'import-datastore-data', 'msg': 'skipped'}
    else:
        _gcloudsql().import_db(datastore_url, datastore_name, import_user=import_user or datastore_name, db_prefix=db_prefix)
        yield {'step': 'import-datastore-data', 'msg': f'Imported Datastore: {datastore_name}'}


def _gcloud():
    return providers_manager.get_provider(cluster_provider_submodule)


def _gcloudsql():
    return db_manager.get_provider()
