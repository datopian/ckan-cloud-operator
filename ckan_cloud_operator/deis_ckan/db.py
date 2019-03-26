import traceback

from ckan_cloud_operator.datastore_permissions import DATASTORE_PERMISSIONS_SQL_TEMPLATE
from ckan_cloud_operator.providers.db import manager as db_manager
from ckan_cloud_operator.providers.ckan.db import migration as ckan_db_migration_manager
from ckan_cloud_operator.drivers.postgres import driver as postgres_driver


class DeisCkanInstanceDb(object):

    def __init__(self, instance, db_type):
        self.instance = instance
        assert db_type in ['db', 'datastore']
        self.db_type = db_type
        self.db_spec = getattr(self.instance.spec, db_type)
        self.db_prefix = self.db_spec.get('dbPrefix')

    def set_datastore_readonly_permissions(self):
        assert self.db_type == 'datastore'
        db_name = self.db_spec['name']
        ro_user = self.instance.annotations.get_secret('datastoreReadonlyUser')
        print(f'setting datastore permissions: {db_name} ({ro_user})')
        with postgres_driver.connect(db_manager.get_external_admin_connection_string(db_name=db_name, db_prefix=self.db_prefix)) as conn:
            with conn.cursor() as cur:
                for line in [
                    f"GRANT CONNECT ON DATABASE \"{db_name}\" TO \"{ro_user}\";",
                    f"GRANT USAGE ON SCHEMA public TO \"{ro_user}\";",
                    f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{ro_user}\";",
                    f"ALTER DEFAULT PRIVILEGES FOR USER \"{db_name}\" IN SCHEMA public GRANT SELECT ON TABLES TO \"{ro_user}\";",
                ]:
                    cur.execute(line)
                # site_user = self.instance.spec.db['name']
                site_user = db_name
                datastore_permissions = DATASTORE_PERMISSIONS_SQL_TEMPLATE.replace('{{SITE_USER}}', site_user).replace('{{DS_RO_USER}}', ro_user)
                try:
                    cur.execute(datastore_permissions)
                except Exception:
                    traceback.print_exc()
                    print('Failed to set datastore sql template, continuing anyway')

    def update(self):
        db_migration_name = self.db_spec.get('fromDbMigration')
        if not db_migration_name:
            db_migration_name = f'new-{self.db_type}-{self.instance.id}'
            db_migration_spec = {
                'type': f'new-{self.db_type}',
                f'{self.db_type}-name': self.db_spec['name'],
                **({'db-prefix': self.db_spec['dbPrefix']} if self.db_spec.get('dbPrefix') else {}),
            }
            migration = ckan_db_migration_manager.create(
                db_migration_name, db_migration_spec, exists_ok=True
            )
            for event in ckan_db_migration_manager.update(migration):
                ckan_db_migration_manager.print_event_exit_on_complete(event, '')
        database_password, datastore_password, datastore_readonly_password = ckan_db_migration_manager.get_dbs_passwords(db_migration_name)
        datastore_readonly_user = ckan_db_migration_manager.get_datastore_raedonly_user_name(db_migration_name)
        if self.db_type == 'db':
            if database_password:
                self.instance.annotations.set_secrets({
                    'databasePassword': database_password
                })
        elif self.db_type == 'datastore':
            if datastore_password and datastore_readonly_password:
                self.instance.annotations.set_secrets({
                    'datastorePassword': datastore_password,
                    'datastoreReadonlyUser': datastore_readonly_user,
                    'datatastoreReadonlyPassword': datastore_readonly_password,
                })

    def get(self):
        return {'ready': db_manager.check_db_exists(self.db_spec['name'], db_prefix=self.db_prefix),
                'db-name': self.db_spec['name'],
                'db-prefix': self.db_prefix}
