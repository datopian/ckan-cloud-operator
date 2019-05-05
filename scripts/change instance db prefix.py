import os
from ruamel import yaml
from ckan_cloud_operator.helpers import scripts as scripts_helpers
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.jenkins import driver as jenkins_driver
from ckan_cloud_operator.providers.ckan import manager as ckan_manager
from ckan_cloud_operator.providers.db.gcloudsql import manager as gcloudsql_manager


INSTANCE_ID, OLD_DB_PREFIX, NEW_DB_PREFIX, DOWN_TIME_APPROVAL_CODE, CHECK_PROGRESS_CODE = scripts_helpers.get_env_vars(
    'INSTANCE_ID', 'OLD_DB_PREFIX', 'NEW_DB_PREFIX', 'DOWN_TIME_APPROVAL_CODE', 'CHECK_PROGRESS_CODE'
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


def main(instance_id, old_db_prefix, new_db_prefix, down_time_approval_code, check_progress_code):
    logs.info(instance_id=instance_id, old_db_prefix=old_db_prefix, new_db_prefix=new_db_prefix,
              down_time_approval_code=down_time_approval_code, check_progress_code=check_progress_code)
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
            kubectl.check_call(f'delete deployment {instance_id} --wait=false', namespace=instance_id)
            logs.info('Creating DB backups')
            assert gcloudsql_manager.create_backup(db_name), 'failed db backup'
            assert gcloudsql_manager.create_backup(datastore_name), 'failed datastore backup'

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
    main(INSTANCE_ID, OLD_DB_PREFIX, NEW_DB_PREFIX, DOWN_TIME_APPROVAL_CODE, CHECK_PROGRESS_CODE)