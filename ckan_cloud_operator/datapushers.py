import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.infra import CkanInfra


def install_crds():
    """Ensures installaion of the datapusher custom resource definitions on the cluster"""
    kubectl.install_crd('ckanclouddatapushers', 'ckanclouddatapusher', 'CkanCloudDatapusher')


def create(name, image, path_to_config_yaml):
    with open(path_to_config_yaml) as f:
        config = yaml.load(f)
    labels =  _get_labels(name)
    datapusher = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudDatapusher', name, labels)
    datapusher['spec'] = {'image': image,
                          'config': config}
    kubectl.create(datapusher)


def update(name):
    _update_registry_secret()
    datapusher = kubectl.get(f'CkanCloudDatapusher {name}')
    deployment_name = get_deployment_name(name)
    labels = _get_labels(name)
    spec = _get_deployment_spec(labels, datapusher['spec'])
    print(f'Updating CkanCloudDatapusher {name} (deployment_name={deployment_name})')
    deployment = kubectl.get_deployment(deployment_name, labels, spec)
    kubectl.apply(deployment)


def delete(name):
    print(f'Deleting datapusher {name}')
    assert kubectl.remove_resource_and_dependencies(
        'CkanCloudDatapusher',
        name,
        ['deployment', 'service'],
        f'ckan-cloud/datapusher-name={name}'
    )


def update_service(name):
    labels = _get_labels(name)
    service = kubectl.get_resource('v1', 'Service', get_service_name(name), labels)
    service['spec'] = {
        'ports': [
            {'name': '8000', 'port': 8000}
        ],
        'selector': labels
    }
    kubectl.apply(service)


def get_service_url(name):
    service_name = get_service_name(name)
    namespace = 'ckan-cloud'
    port = 8000
    return f'http://{service_name}.{namespace}:{port}'


def get(name, deployment=None, full=False):
    deployment_name = get_deployment_name(name)
    if not deployment:
        deployment = kubectl.get(f'deployment {deployment_name}', required=False)
    if deployment:
        deployment_status = kubectl.get_deployment_detailed_status(
            deployment,
            f'ckan-cloud/datapusher-name={name}',
            'datapusher'
        )
        ready = bool(len(deployment_status.get('errors', [])) == 0)
    else:
        deployment_status = {}
        ready = False
    if full:
        return {
            'ready': ready,
            'name': name,
            **deployment_status
        }
    else:
        return {
            'ready': ready,
            'name': name
        }


def list(full=False):
    return [get(datapusher['metadata']['name'], full=full) for datapusher in kubectl.get('CkanCloudDatapusher')['items']]


def _get_labels(name):
    return {'ckan-cloud/datapusher-name': name}


def get_deployment_name(name):
    return name if name.startswith('datapusher') else f'datapusher-{name}'


def get_service_name(name):
    return get_deployment_name(name)


def _get_deployment_spec(labels, spec):
    deployment_spec = {
        'replicas': 1,
        'revisionHistoryLimit': 10,
        'template': {
            'metadata': {
                'labels': labels
            },
            'spec': {
                'imagePullSecrets': [
                    {'name': 'datapushers-docker-registry'}
                ],
                'containers': [
                    {
                        'name': 'datapusher',
                        'image': spec['image'],
                        'env': [
                            *_get_deployment_pod_envvars(spec['config']),
                        ],
                        'readinessProbe': {
                            'failureThreshold': 1,
                            'initialDelaySeconds': 5,
                            'periodSeconds': 5,
                            'successThreshold': 1,
                            'tcpSocket': {
                                'port': 8000
                            },
                            'timeoutSeconds': 5
                        }
                    }
                ]
            }
        }
    }
    kubectl.add_operator_timestamp_annotation(deployment_spec['template']['metadata'])
    return deployment_spec


def _get_deployment_pod_envvars(config):
    return [{'name': k, 'value': v} for k, v in config.items()]


def _update_registry_secret():
    secret = kubectl.get('secret datapushers-docker-registry', required=False)
    if secret:
        print('Secret already exists, delete to recreate: datapushers-registry-secret')
    else:
        ckan_infra = CkanInfra()
        print('Creating datapushers registry secret')
        docker_server = ckan_infra.DOCKER_REGISTRY_SERVER
        docker_username = ckan_infra.DOCKER_REGISTRY_USERNAME
        docker_password = ckan_infra.DOCKER_REGISTRY_PASSWORD
        docker_email = ckan_infra.DOCKER_REGISTRY_EMAIL
        kubectl.check_call(f'create secret docker-registry datapushers-docker-registry '
                           f'--docker-password={docker_password} '
                           f'--docker-server={docker_server} '
                           f'--docker-username={docker_username} '
                           f'--docker-email={docker_email}')
