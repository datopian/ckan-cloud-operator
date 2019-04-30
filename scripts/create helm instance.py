import os
import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.providers.ckan.instance import manager as ckan_instance_manager


instance_type = 'helm'

instance_id = os.environ.get('INSTANCE_ID')

instance_name = os.environ.get('INSTANCE_NAME')

values_yaml = os.environ.get('VALUES_YAML')
assert values_yaml
values = yaml.load(values_yaml)

exists_ok = os.environ.get('EXISTS_OK')
exists_ok = exists_ok == 'yes'

dry_run = os.environ.get('DRY_RUN')
dry_run = dry_run == 'yes'

update = os.environ.get('UPDATE')
update = update == 'yes'

wait_ready = os.environ.get('WAIT_READY')
wait_ready = wait_ready == 'yes'


instance_id = ckan_instance_manager.create(
    instance_type=instance_type, instance_id=instance_id, instance_name=instance_name,
    values=values, exists_ok=exists_ok, dry_run=dry_run
)


if update:
    if dry_run:
        raise Exception('dry run is not supported with update')
    else:
        ckan_instance_manager.update(instance_id, wait_ready=wait_ready)
