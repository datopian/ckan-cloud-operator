import os
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.apps import manager as apps_manager


instance_id_or_name = os.environ.get('INSTANCE_ID_OR_NAME')

attr = os.environ.get('ATTR')

with_spec = os.environ.get('WITH_SPEC')
with_spec = with_spec == 'yes'


logs.print_yaml_dump(
    apps_manager.get(instance_id_or_name=instance_id_or_name, attr=attr, with_spec=with_spec),
    exit_success=True
)
