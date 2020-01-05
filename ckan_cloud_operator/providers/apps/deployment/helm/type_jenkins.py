from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs


DEFAULT_CHART_VALUES = {
    'chart-repo-name': 'stable',
    'chart-name': 'stable/jenkins',
}

DEFAULT_VALUES = {
    'Agent': {
        'Enabled': False,
    },
    'Master': {
        'ServiceType': 'ClusterIP',
    },
    'Persistence': {
        'Size': '100Gi',
        'StorageClass': 'cca-ckan'
    }
}


def pre_update_hook(instance_id, instance, res, sub_domain, root_domain, modify_spec_callback):
    logs.info('jenkins pre_update_hook', instance_id=instance_id, instance_spec=instance.get('spec'))
    chart_update_kwargs = {
        k: v for k, v in DEFAULT_CHART_VALUES.items()
        if not instance['spec'].get(k)
    }
    values_update_kwargs = {
        k: v for k, v in DEFAULT_VALUES.items()
        if not instance['spec'].get('values', {}).get(k)
    }
    logs.debug(chart_update_kwargs=chart_update_kwargs)
    logs.debug(values_update_kwargs=values_update_kwargs)
    instance['spec'].update(**chart_update_kwargs)
    instance['spec'].setdefault('values', {}).update(**values_update_kwargs)
    modify_spec_callback(lambda i: i.update(**chart_update_kwargs))
    modify_spec_callback(lambda i: i.setdefault('values', {}).update(**values_update_kwargs))


def pre_deploy_hook(instance_id, instance, deploy_kwargs):
    pass


def post_deploy_hook(instance_id, instance, deploy_kwargs):
    kubectl.apply(kubectl.get_deployment(
        name='jnlp-kube-prod-1',
        labels={},
        spec={
            'minReadySeconds': 15, 'progressDeadlineSeconds': 1200, 'replicas': 1,
            'revisionHistoryLimit': 10,
            'selector': {
                'matchLabels': {
                    'app': 'deployment-jenkins-jnlp-kube-prod-1'
                }
            },
            'strategy': {
                'type': 'Recreate'
            },
            'template': {
                'metadata': {
                    'labels': {
                        'app': 'deployment-jenkins-jnlp-kube-prod-1'
                    }
                },
                'spec': {
                    'containers': [
                        {
                            'command': ['bash', '/home/jenkins/ckan-cloud-operator/entrypoint-jnlp.sh'],
                            'env': [
                                {'name': 'CKAN_CLOUD_OPERATOR_SCRIPTS', 'value': '/usr/src/ckan-cloud-operator/scripts'},
                                {'name': 'CKAN_CLOUD_USER_NAME', 'value': 'jenkins-admin'},
                                {'name': 'HOME', 'value': '/home/jenkins/agent'}
                            ],
                            'envFrom': [
                                {'secretRef': {'name': 'jnlp-slave-kube-prod-1', 'optional': False}}
                            ],
                            'image': 'viderum/ckan-cloud-operator:jnlp-v0.2.7',
                            'imagePullPolicy': 'Always',
                            'name': 'jnlp-kube-prod-1',
                            'resources': {},
                            'volumeMounts': [
                                {'mountPath': '/etc/ckan-cloud', 'name': 'vol1'},
                                {'mountPath': '/home/jenkins/agent', 'name': 'workspace-volume'}
                            ],
                            'workingDir': '/home/jenkins/agent'
                        }
                    ],
                    'terminationGracePeriodSeconds': 120,
                    'volumes': [
                        {
                            'name': 'vol1',
                            'secret': {
                                'defaultMode': 511, 'optional': False, 'secretName': 'etc-ckan-cloud-jenkins-admin'
                            }
                        },
                        {
                            'emptyDir': {},
                            'name': 'workspace-volume'}
                    ]
                }
            }
        },
        namespace=instance_id,
    ))
    pass


def pre_delete_hook(instance_id, instance, delete_kwargs):
    pass


def post_delete_hook(instance_id, instance, delete_kwargs):
    pass


def get_backend_url(instance_id, instance, backend_url):
    release_name = instance['spec'].get('release-name')
    if release_name:
        return f'http://{release_name}-jenkins.{instance_id}:8080'
    else:
        return None


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
    if 'jenkins' not in app_pods_status:
        res['ready'] = False
    res['app'] = {
        'pods': app_pods_status,
        'deployments': app_deployments_status
    }
