from ckan_cloud_operator import kubectl


DEFAULT_CHART_VALUES = {
    'chart-repo': 'https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-helm/master/charts_repository',
    'chart-repo-name': 'ckan-cloud',
    'chart-name': 'ckan-cloud/elk',
    'chart-version': 'v0.0.2',
}

DEFAULT_VALUES = {
    'elasticsearchMemoryLimit': '3Gi',
    'elasticsearchStorage': '300Gi',
    'elsaticsearchReplicas': 2,
    'logstashMemoryLimit': '1.5Gi',
    'storageclassProvisioner': 'kubernetes.io/aws-ebs'
}


def pre_update_hook(instance_id, instance, res, sub_domain, root_domain, modify_spec_callback):
    modify_spec_callback(lambda i: i.update(**{
        k: v for k, v in DEFAULT_CHART_VALUES.items()
        if not instance['spec'].get(k)
    }))
    modify_spec_callback(lambda i: i.setdefault('values', {}).update(**{
        k: v for k, v in DEFAULT_VALUES.items()
        if not instance['spec'].get('values', {}).get(k)
    }))


def pre_deploy_hook(instance_id, instance, deploy_kwargs):
    pass


def post_deploy_hook(instance_id, instance, deploy_kwargs):
    pass


def pre_delete_hook(instance_id, instance, delete_kwargs):
    pass


def post_delete_hook(instance_id, instance, delete_kwargs):
    pass


def get_backend_url(instance_id, instance, backend_url):
    return 'http://kibana.elk:80'


def get(instance_id, instance, res):
    res['ready'] = True
    app_pods_status = {}
    for pod in kubectl.get('pods', namespace=instance_id, required=True)['items']:
        app = pod['metadata']['labels'].get('app')
        if not app:
            app = 'unknown'
        item_status = kubectl.get_item_detailed_status(pod)
        if item_status.get('errors') and len(item_status['errors']) > 0:
            res['ready'] = False
        app_pods_status.setdefault(app, {})[pod['metadata']['name']] = item_status
    app_deployments_status = {}
    for deployment in kubectl.get('deployments', namespace=instance_id, required=True)['items']:
        app = deployment['metadata']['labels'].get('app')
        if not app:
            app = 'unknown'
        item_status = kubectl.get_item_detailed_status(deployment)
        if item_status.get('errors') and len(item_status['errors']) > 0:
            res['ready'] = False
        app_deployments_status.setdefault(app, {})[deployment['metadata']['name']] = item_status
    if 'api' not in app_pods_status or 'ui' not in app_pods_status:
        res['ready'] = False
    res['app'] = {
        'pods': app_pods_status,
        'deployments': app_deployments_status
    }
