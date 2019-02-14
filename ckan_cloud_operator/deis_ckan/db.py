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

    def set_datastore_readonly_permissions(self):
        assert self.db_type == 'datastore'
        db_name = self.db_spec['name']
        ro_user = self.instance.annotations.get_secret('datastoreReadonlyUser')
        print(f'setting datastore permissions: {db_name} ({ro_user})')
        with postgres_driver.connect(db_manager.get_external_admin_connection_string(db_name=db_name)) as conn:
            with conn.cursor() as cur:
                for line in [
                    # f"REVOKE CREATE ON SCHEMA public FROM PUBLIC;",
                    # f"REVOKE USAGE ON SCHEMA public FROM PUBLIC;",
                    # f"GRANT CREATE ON SCHEMA public TO \"{site_user}\";",
                    # f"GRANT USAGE ON SCHEMA public TO \"{site_user}\";",
                    # f"GRANT CREATE ON SCHEMA public TO \"{db_name}\";",
                    # f"GRANT USAGE ON SCHEMA public TO \"{db_name}\";",
                    # f"GRANT \"{site_user}\" TO \"{postgres_user}\";",
                    # f"ALTER DATABASE \"{site_user}\" OWNER TO {postgres_user};",
                    # f"ALTER DATABASE \"{db_name}\" OWNER TO {postgres_user};",
                    # f"REVOKE CONNECT ON DATABASE \"{site_user}\" FROM \"{ro_user}\";",
                    f"GRANT CONNECT ON DATABASE \"{db_name}\" TO \"{ro_user}\";",
                    f"GRANT USAGE ON SCHEMA public TO \"{ro_user}\";",
                    # f"ALTER DATABASE \"{site_user}\" OWNER TO \"{site_user}\";",
                    # f"GRANT \"{db_name}\" TO \"{postgres_user}\";",
                    # f"ALTER DATABASE \"{db_name}\" OWNER TO \"{db_name}\";",
                    f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{ro_user}\";",
                    f"ALTER DEFAULT PRIVILEGES FOR USER \"{db_name}\" IN SCHEMA public GRANT SELECT ON TABLES TO \"{ro_user}\";",
                    # f"GRANT \"{site_user}\" to \"{db_name}\";",
                    # f"REASSIGN OWNED BY \"{postgres_user}\" TO \"{db_name}\";",
                ]:
                    cur.execute(line)
                site_user = self.instance.spec.db['name']
                datastore_permissions = DATASTORE_PERMISSIONS_SQL_TEMPLATE.replace('{{SITE_USER}}', site_user).replace('{{DS_RO_USER}}', ro_user)
                cur.execute(datastore_permissions)

    def update(self):
        db_migration_name = self.db_spec.get('fromDbMigration')
        assert db_migration_name, 'only import from a db migration is supported'
        database_password, datastore_password, datastore_readonly_password = ckan_db_migration_manager.get_dbs_passwords(db_migration_name, required=True)
        if self.db_type == 'db':
            assert database_password
            self.instance.annotations.set_secrets({
                'databasePassword': database_password
            })
        elif self.db_type == 'datastore':
            assert datastore_password and datastore_readonly_password
            self.instance.annotations.set_secrets({
                'datastorePassword': datastore_password,
                'datastoreReadonlyUser': ckan_db_migration_manager.get_datastore_raedonly_user_name(db_migration_name, required=True),
                'datatastoreReadonlyPassword': datastore_readonly_password,
            })
        # is_created = self.instance.annotations.update_status(self.db_type, 'created', lambda: self._create())
        # skip_permissions_flag = 'skipDatastorePermissions' if self.db_type == 'datastore' else 'skipDbPermissions'
        # if is_created or not self.instance.annotations.get_flag(skip_permissions_flag):
        #     db_manager.update(deis_instance_id=self.instance.id)
        #     self._set_db_permissions()
        #     if self.db_type == 'datastore':
        #         self._set_datastore_permissions()
        # if is_created:
        #     self.instance.annotations.set_flag(skip_permissions_flag)

    # def delete(self):
    #     db_name = self.db_spec['name']
    #     self._psql(f'DROP DATABASE IF EXISTS "{db_name}";')
        # TODO: get the ro_user from the instance annotations
        # self._psql(f'DROP ROLE IF EXISTS "{db_name}";')
        # self._psql(f'DROP ROLE IF EXISTS "{db_name}-ro";')

    def get(self):
        return {'ready': db_manager.check_db_exists(self.db_spec['name'])}
        # print(db_name)
        # try:
        #     self._psql('select 1', '-d', db_name, '-q', '-o', '/dev/null')
        #     return {'ready': True}
        # except Exception:
        #     traceback.print_exc()
        #     return {'ready': False}
        # gcloud sql commands related to DBs don't work due to missing permissions to gcloud account
        # TODO: allow to run gcloud db commands
        # exitcode, output = gcloud.getstatusoutput(
        #     f'-q sql databases describe {db_name} --instance {gcloud_sql_instance_name}',
        #     ckan_infra=self.instance.ckan_infra
        # )
        # if exitcode == 0:
        #     gcloud_status = yaml.load(output)
        #     assert gcloud_status['instance'] == gcloud_sql_instance_name
        #     assert gcloud_status['name'] == db_name
        #     assert gcloud_status['project'] == gcloud_sql_project
        #     return {'ready': True,
        #             'name': db_name,
        #             'selfLink': gcloud_status['selfLink']}
        # else:
        #     return {'ready': False,
        #             'name': db_name,
        #             'gcloud_sql_instance_name': gcloud_sql_instance_name,
        #             'gcloud_sql_project': gcloud_sql_project,
        #             'error': output}

    # def _create(self):
    #     print(f'Creating {self.db_type}')
    #     if 'fromDeisInstance' in self.db_spec:
    #         raise NotImplementedError('import of DB from old deis instance id is not supported yet')
    #     else:
    #         self._create_base_db()
    #         db_manager.update(deis_instance_id=self.instance.id)
    #         db_name = self.db_spec['name']
    #         if self.db_type == 'db':
    #             self._initialize_db_postgis(db_name)
    #         if 'importGcloudSqlDumpUrl' in self.db_spec:
    #             self._import_gcloud_sql_db()
    #         if self.db_type == 'datastore':
    #             self._create_datastore_ro_user()


    # def _set_db_permissions(self):
    #     print('setting db permissions')
    #     db_name = self.db_spec['name']
    #     postgres_user = self.instance.ckan_infra.POSTGRES_USER
    #     for line in [
    #         f"GRANT \"{db_name}\" TO \"{postgres_user}\";",
    #         f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" to "{db_name}";',
    #         f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public to "{db_name}";',
    #         f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to "{db_name}";',
    #         f'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public to "{db_name}";',
    #         f'alter default privileges in schema public grant all on tables to "{db_name}";',
    #         f'alter default privileges in schema public grant all on sequences to "{db_name}";',
    #         f'alter default privileges in schema public grant all on functions to "{db_name}";',
    #         f"ALTER DATABASE \"{db_name}\" OWNER TO \"{db_name}\";",
    #     ]:
    #         self._psql(line, '-d', db_name)
