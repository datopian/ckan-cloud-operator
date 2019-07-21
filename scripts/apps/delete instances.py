import os
import tempfile
from ruamel import yaml
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.apps import manager as apps_manager
from dataflows import Flow, dump_to_path, printer
from ckan_cloud_operator.helpers import scripts as scripts_helpers


# id or name of instances to delete
INSTANCE_IDS_OR_NAMES = os.environ.get('INSTANCE_IDS_OR_NAMES', '')

# keep empty to do a dry run and get the code from the output
APPROVE_CODE = os.environ.get('APPROVE_CODE', '')


def delete_instances(instance_ids_or_names, approve_code):
    # scripts_helpers.check_file_based_approval_code(approve_code)
    dry_run_generator = apps_manager.delete_instances(instance_ids_or_names=instance_ids_or_names, dry_run=True)
    instance_ids = set()
    instance_names = set()
    while True:
        try:
            instance = next(dry_run_generator)
            if instance.get('id'):
                instance_ids.add(instance['id'])
            if instance.get('name'):
                instance_ids.add(instance['name'])
            logs.info("dry run", **instance)
        except StopIteration:
            break
        res = next(dry_run_generator)
        logs.info("dry run", **res)
        yield {"dry-run": True, **instance, **res}
    if approve_code:
        assert scripts_helpers.check_file_based_approval_code(approve_code, {'instance-ids': instance_ids}), \
            'invalid approval code'
        generator = apps_manager.delete_instances(instance_ids_or_names=instance_ids, dry_run=False)
        while True:
            try:
                instance = next(generator)
                logs.info('Deleting instance', **instance)
            except StopIteration:
                break
            res = next(generator)
            logs.info(**res)
            yield {"dry-run": False, **instance, **res}
    else:
        approve_code = scripts_helpers.create_file_based_approval_code({'instance-ids': instance_ids})
        logs.important_log(logs.INFO, f'APPROVE_CODE={approve_code}', instance_ids=instance_ids)


def main(instance_ids_or_names, approve_code):
    instance_ids_or_names = [i.strip() for i in instance_ids_or_names.split(',') if i.strip()]
    approve_code = approve_code.strip()
    logs.info(instance_ids_or_names=instance_ids_or_names, approve_code=approve_code)
    Flow(
        delete_instances(instance_ids_or_names, approve_code),
        dump_to_path('data/apps/delete_instances'),
        printer(num_rows=9999)
    ).process()


if __name__ == '__main__':
    main(INSTANCE_IDS_OR_NAMES, APPROVE_CODE)
