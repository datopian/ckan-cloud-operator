from ckan_cloud_operator.helpers import scripts as scripts_helpers
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.routers import manager as routers_manager


OLD_INSTANCE_ID, NEW_INSTANCE_ID, DRY_RUN = scripts_helpers.get_env_vars(
    'OLD_INSTANCE_ID', 'NEW_INSTANCE_ID', 'DRY_RUN'
)


def _assert_set(data, key, old_value, new_value):
    assert data[key] == old_value
    data[key] = new_value


def main(old_instance_id, new_instance_id, dry_run):
    dry_run = (dry_run == 'yes')
    router_names = set()
    for route in routers_manager.get_deis_instance_routes(old_instance_id):
        for label in ['ckan-cloud/route-deis-instance-id', 'ckan-cloud/route-target-resource-id']:
            _assert_set(route['metadata']['labels'], label, old_instance_id, new_instance_id)
        for attr in ['deis-instance-id', 'route-target-resource-id']:
            _assert_set(route['spec'], attr, old_instance_id, new_instance_id)
        kubectl.apply(route, dry_run=dry_run)
        router_names.add(route['spec']['router_name'])
    logs.info('updating routers', router_names=router_names)
    if not dry_run:
        for router_name in router_names:
            routers_manager.update(router_name)


if __name__ == '__main__':
    main(OLD_INSTANCE_ID, NEW_INSTANCE_ID, DRY_RUN)
