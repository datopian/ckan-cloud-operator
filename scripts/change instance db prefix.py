import datetime
from ruamel import yaml
from ckan_cloud_operator.helpers import scripts as scripts_helpers
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.jenkins import driver as jenkins_driver
from ckan_cloud_operator.providers.ckan import manager as ckan_manager
from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.drivers.gcloud import driver as gcloud_driver
from ckan_cloud_operator.config import manager as config_manager


INSTANCE_ID, OLD_DB_PREFIX, NEW_DB_PREFIX, DOWN_TIME_APPROVAL_CODE, NEW_INSTANCE_ID, GITLAB_REPO, SOLR_COLLECTION_NAME, STORAGE_PATH = scripts_helpers.get_env_vars(
    'INSTANCE_ID', 'OLD_DB_PREFIX', 'NEW_DB_PREFIX', 'DOWN_TIME_APPROVAL_CODE', 'NEW_INSTANCE_ID', 'GITLAB_REPO',
    'SOLR_COLLECTION_NAME', 'STORAGE_PATH'
)


def _create_down_time_approval_code(instance_id, old_db_prefix, new_db_prefix, db_name, datastore_name):
    jenkins_user_token = ckan_manager.get_jenkins_token('ckan-cloud-operator-jenkins-creds')
    backups_console_log = jenkins_driver.curl(
        *jenkins_user_token,
        'https://cc-p-jenkins.ckan.io/job/check%20individual%20DB%20backups/lastBuild/console',
        raw=True
    )
    backups_console_log = backups_console_log.split('Finished: SUCCESS')[0].split('Updated property [compute/zone].')[1]
    backups = yaml.safe_load(backups_console_log)
    backups = {k: v for k, v in backups.items()
               if (
                       k == db_name or k == datastore_name
                       or k == f'{db_name}-total-size'
                       or k == f'{datastore_name}-total-size'
               )}
    logs.info('last instance backups')
    logs.print_yaml_dump(backups)
    return scripts_helpers.create_file_based_approval_code({
        'instance-id': instance_id,
        'old-db-prefix': old_db_prefix,
        'new-db-prefix': new_db_prefix,
        'db-name': db_name,
        'datastore-name': datastore_name
    })


def _check_down_time_approval_code(instance_id, old_db_prefix, new_db_prefix, down_time_approval_code, db_name,
                                   datastore_name):
    assert scripts_helpers.check_file_based_approval_code(down_time_approval_code, {
        'instance-id': instance_id,
        'old-db-prefix': old_db_prefix,
        'new-db-prefix': new_db_prefix,
        'db-name': db_name,
        'datastore-name': datastore_name
    }), 'invalid down time approval code'


def _get_latest_backups(db_name, datastore_name):
    gs_base_url = config_manager.get(key='backups-gs-base-url', secret_name='ckan-cloud-provider-db-gcloudsql-credentials')
    output = gcloud_driver.check_output(
        *cluster_manager.get_provider().get_project_zone(),
        f"ls {gs_base_url}/`date +%Y/%m/%d`/'*'/ | grep {db_name}", gsutil=True
    ).decode() + '\n' + gcloud_driver.check_output(
        *cluster_manager.get_provider().get_project_zone(),
        f"ls {gs_base_url}/`date +%Y/%m/%d`/'*'/ | grep {datastore_name}", gsutil=True
    ).decode()
    datastore_backup_url, datastore_backup_datetime = None, None
    db_backup_url, db_backup_datetime = None, None
    for line in output.splitlines():
        line = line.strip()
        if len(line) < 10: continue
        backup_name, backup_datetime = line.split('/')[-1].split('.')[0].split('_')
        backup_datetime = datetime.datetime.strptime(backup_datetime, '%Y%m%d%H%M')
        if backup_name == db_name:
            is_datastore = False
        elif backup_name == datastore_name:
            is_datastore = True
        else:
            continue
        logs.info(backup_name=backup_name, backup_datetime=backup_datetime, is_datastore=is_datastore)
        if is_datastore and (datastore_backup_datetime is None or datastore_backup_datetime < backup_datetime):
            datastore_backup_datetime, datastore_backup_url = backup_datetime, line
        if not is_datastore and (db_backup_datetime is None or db_backup_datetime < backup_datetime):
            db_backup_datetime, db_backup_url = backup_datetime, line
    logs.info(db_backup_datetime=db_backup_datetime, db_backup_url=db_backup_url)
    logs.info(datastore_backup_datetime=datastore_backup_datetime, datastore_backup_url=datastore_backup_url)
    return db_backup_url, datastore_backup_url


def main(instance_id, old_db_prefix, new_db_prefix, down_time_approval_code, new_instance_id, gitlab_repo, solr_collection_name, storage_path):
    logs.info(instance_id=instance_id, old_db_prefix=old_db_prefix, new_db_prefix=new_db_prefix,
              down_time_approval_code=down_time_approval_code)
    instance = kubectl.get('ckancloudckaninstance', instance_id)
    current_db_prefix = instance['spec']['db'].get('dbPrefix', 'prod')
    current_datastore_prefix = instance['spec']['datastore'].get('dbPrefix', 'prod')
    assert current_db_prefix == current_datastore_prefix, 'different prefix for datastore and DB is not supported yet'
    db_name = instance['spec']['db']['name']
    datastore_name = instance['spec']['datastore']['name']
    logs.info(current_db_prefix=current_db_prefix, db_name=db_name,
              current_datastore_prefix=current_datastore_prefix, datastore_name=datastore_name)
    if current_db_prefix == old_db_prefix:
        if down_time_approval_code:
            _check_down_time_approval_code(instance_id, old_db_prefix, new_db_prefix, down_time_approval_code,
                                           db_name, datastore_name)
            logs.info(f'Deleting instance deployment (namespace={instance_id} deployment={instance_id}')
            kubectl.call(f'delete deployment {instance_id} --wait=false', namespace=instance_id)
            logs.info('Creating DB backups')
            assert gcloudsql_manager.create_backup(db_name), 'failed db backup'
            assert gcloudsql_manager.create_backup(datastore_name), 'failed datastore backup'
            db_backup_url, datastore_backup_url = _get_latest_backups(db_name, datastore_name)
            logs.important_log(logs.INFO, db_backup_url=db_backup_url)
            logs.important_log(logs.INFO, datastore_backup_url=datastore_backup_url)
            logs.info('Creating parameters file to trigger copy instance job to create the new instance')
            with open('copy_instance_params', 'w') as f:
                f.write(f'OLD_INSTANCE_ID={instance_id}\n'
                        f'NEW_INSTANCE_ID={new_instance_id}\n'
                        f'NEW_GITLAB_REPO={gitlab_repo}\n'
                        f'NEW_DB_PREFIX={new_db_prefix}\n'
                        f'IMPORT_DATE_PATH=\n'
                        f'IMPORT_HOUR=\n'
                        f'SKIP_MINIO_MIRROR=no\n'
                        f'SKIP_CREATE=no\n'
                        f'SKIP_ROUTER=no\n'
                        f'USE_EXISTING_MIGRATION=no\n'
                        f'NEW_SOLR_COLLECTION_NAME={solr_collection_name}\n'
                        f'NEW_STORAGE_PATH={storage_path}\n'
                        f'DATABASE_IMPORT_URL={db_backup_url}\n'
                        f'DATASTORE_IMPORT_URL={datastore_backup_url}\n'
                        f'DRY_RUN=yes\n'
                        )
            logs.exit_great_success()
        else:
            down_time_approval_code = _create_down_time_approval_code(
                instance_id, old_db_prefix, new_db_prefix,
                db_name, datastore_name
            )
            logs.important_log(logs.INFO, f'DOWN_TIME_APPROVAL_CODE={down_time_approval_code}')
            logs.exit_great_success(quiet=True)
    else:
        raise NotImplementedError()


if __name__ == '__main__':
    main(INSTANCE_ID, OLD_DB_PREFIX, NEW_DB_PREFIX, DOWN_TIME_APPROVAL_CODE, NEW_INSTANCE_ID, GITLAB_REPO, SOLR_COLLECTION_NAME, STORAGE_PATH)
