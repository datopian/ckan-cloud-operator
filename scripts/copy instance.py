import sys
import subprocess
import os
import datetime
import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
from ckan_cloud_operator.providers.ckan.db import migration as ckan_db_migration
from ckan_cloud_operator.providers.ckan import manager as ckan_manager

old_instance_id = os.environ['OLD_INSTANCE_ID']
new_instance_id = os.environ['NEW_INSTANCE_ID']
new_gitlab_repo = os.environ['NEW_GITLAB_REPO']
new_db_prefix = os.environ['NEW_DB_PREFIX']
new_solr_collection_name = os.environ['NEW_SOLR_COLLECTION_NAME']
new_storage_path = os.environ['NEW_STORAGE_PATH']
database_import_url = os.environ['DATABASE_IMPORT_URL']
datastore_import_url = os.environ['DATASTORE_IMPORT_URL']
dry_run = (os.environ['DRY_RUN'] == 'yes')

gs_base_url = config_manager.get(secret_name='ckan-cloud-provider-db-gcloudsql-credentials', key='backups-gs-base-url')
logs.info(gs_base_url=gs_base_url)

old_instance = DeisCkanInstance(old_instance_id)

old_db_prefix = old_instance.spec.db.get('dbPrefix', '')
if not old_db_prefix or old_db_prefix == 'prod1':
    dbprefixpath = ''
else:
    dbprefixpath = '/' + old_db_prefix
assert old_db_prefix == old_instance.spec.datastore.get('dbPrefix',
                                                        ''), 'different db prefix for db and datastore is not supported'

old_db_name = old_instance.spec.db['name']
old_datastore_name = old_instance.spec.datastore['name']
logs.info(old_db_name=old_db_name, old_datastore_name=old_datastore_name, old_db_prefix=old_db_prefix)

old_db_url, old_datastore_url = None, None

if database_import_url:
    old_db_url = database_import_url
    assert datastore_import_url

if datastore_import_url:
    old_datastore_url = datastore_import_url
    assert database_import_url

if not old_db_url and not old_datastore_url:
    if os.environ.get('IMPORT_DATE_PATH'):
        datepath = os.environ['IMPORT_DATE_PATH']
    else:
        datepath = datetime.datetime.now().strftime('%Y/%m/%d')
    if os.environ.get('IMPORT_HOUR'):
        hours = [int(os.environ['IMPORT_HOUR'])]
    else:
        hours = reversed(range(25))
    for hour in hours:
        print(f'looking for backups in ({dbprefixpath}/{datepath}/{hour:02d})', file=sys.__stderr__)
        try:
            old_db_url = subprocess.check_output(
                f'gsutil ls "{gs_base_url}{dbprefixpath}/{datepath}/{hour:02d}/{old_db_name}_"' + "'*'", shell=True)
            old_datastore_url = subprocess.check_output(
                f'gsutil ls "{gs_base_url}{dbprefixpath}/{datepath}/{hour:02d}/{old_datastore_name}_"' + "'*'",
                shell=True)
        except Exception:
            continue
        if old_db_url and old_datastore_url:
            break
    old_db_url = old_db_url.decode().strip()
    old_datastore_url = old_datastore_url.decode().strip()

logs.info(old_db_url=old_db_url, old_datastore_url=old_datastore_url)

assert old_db_url and old_datastore_url, 'failed to find backup files'

old_storage_path = old_instance.spec.storage['path']
logs.info(old_storage_path=old_storage_path)

if not new_storage_path:
    logs.info('Creating new storage path')
    new_storage_path = f'/ckan/{new_instance_id}'
    logs.info(new_storage_path=new_storage_path)
    minio = config_manager.get(secret_name='ckan-cloud-provider-storage-minio')
    if not dry_run:
        subprocess.check_call(
            ['mc', 'config', 'host', 'add', 'prod', 'https://cc-p-minio.ckan.io', minio['MINIO_ACCESS_KEY'],
             minio['MINIO_SECRET_KEY']])
        if os.environ.get('SKIP_MINIO_MIRROR') != 'yes':
            subprocess.check_call(['mc', 'mirror', f'prod{old_storage_path}', f'prod{new_storage_path}'])
            subprocess.check_call(['mc', 'policy', 'download', f'prod{new_storage_path}/storage'])
        subprocess.check_call(['mc', 'ls', f'prod{new_storage_path}'])

solr_config = old_instance.spec.solrCloudCollection['configName']

print('new_instance_id', new_instance_id, file=sys.__stderr__)
print('old_db_url', old_db_url, file=sys.__stderr__)
print('old_datastore_url', old_datastore_url, file=sys.__stderr__)
print('solr_config', solr_config, file=sys.__stderr__)
print('new_storage_path', new_storage_path, file=sys.__stderr__)

new_db_name = new_instance_id
new_datastore_name = f'{new_instance_id}-datastore'

print('new_db_name', new_db_name, file=sys.__stderr__)
print('new_datastore_name', new_datastore_name, file=sys.__stderr__)

migration_name = None
if os.environ.get('USE_EXISTING_MIGRATION') == 'yes':
    for migration in ckan_db_migration.get()['items']:
        if migration.get('spec', {}).get('db-name') == new_db_name:
            migration_name = migration['spec']['name']
            break
elif not dry_run:
    success = False
    for event in ckan_db_migration.migrate_deis_dbs(None, new_db_name, new_datastore_name, db_import_url=old_db_url,
                                                    datastore_import_url=old_datastore_url, db_prefix=new_db_prefix):
        migration_name = ckan_db_migration.get_event_migration_created_name(event) or migration_name
        success = ckan_db_migration.print_event_exit_on_complete(event,
                                                                 f'DBs import -> {new_db_name}, {new_datastore_name}',
                                                                 soft_exit=True)
        if success is not None:
            break
    assert success, f'Invalid DB migration success value ({success})'

print('migration_name', migration_name, file=sys.__stderr__)

if not new_solr_collection_name:
    new_solr_collection_name = new_instance_id
logs.info(new_solr_collection_name=new_solr_collection_name)

spec = {
    'ckanPodSpec': {},
    'ckanContainerSpec': {'imageFromGitlab': new_gitlab_repo},
    'envvars': {'fromGitlab': new_gitlab_repo},
    'solrCloudCollection': {
        'name': new_solr_collection_name,
        'configName': solr_config
    },
    'db': {
        'name': new_db_name,
        **({'fromDbMigration': migration_name} if migration_name else {}),
        **({'dbPrefix': new_db_prefix} if new_db_prefix else {})
    },
    'datastore': {
        'name': new_datastore_name,
        **({'fromDbMigration': migration_name} if migration_name else {}),
        **({'dbPrefix': new_db_prefix} if new_db_prefix else {})
    },
    'storage': {
        'path': new_storage_path,
    }
}
print('spec', spec, file=sys.__stderr__)

if os.environ.get('SKIP_CREATE') != 'yes':
    instance_kind = ckan_manager.instance_kind()
    instance = {
        'apiVersion': f'stable.viderum.com/v1',
        'kind': instance_kind,
        'metadata': {
            'name': new_instance_id,
            'namespace': 'ckan-cloud',
            'finalizers': ['finalizer.stable.viderum.com']
        },
        'spec': spec
    }
    kubectl.apply(instance, dry_run=dry_run)
    if not dry_run:
        DeisCkanInstance(new_instance_id, values=instance).update()

if os.environ.get('SKIP_ROUTER') != 'yes':
    cmd = ['ckan-cloud-operator', 'routers', 'create-deis-instance-subdomain-route', 'instances-default',
           new_instance_id, '--wait-ready']
    print(cmd, file=sys.__stderr__)
    if not dry_run:
        subprocess.check_call(cmd)
