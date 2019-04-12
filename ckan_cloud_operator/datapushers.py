import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.config import manager as config_manager

def add_cli_commands(click, command_group, great_success):

    @command_group.command('initialize')
    def datapushers_initialize():
        initialize()
        great_success()

    @command_group.command('create')
    @click.argument('DATAPUSHER_NAME')
    @click.argument('DOCKER_IMAGE')
    @click.argument('PATH_TO_CONFIG_YAML')
    def datapushers_create(datapusher_name, docker_image, path_to_config_yaml):
        """Create and update a DataPusher deployment

        Example:

            ckan-cloud-operator datapushers create datapusher-1 registry.gitlab.com/viderum/docker-datapusher:cloud-datapusher-1-v9 /path/to/datapusher-1.yaml
        """
        create(datapusher_name, docker_image, path_to_config_yaml)
        update(datapusher_name)
        great_success()

    @command_group.command('update')
    @click.argument('DATAPUSHER_NAME')
    def datapushers_update(datapusher_name):
        update(datapusher_name)
        great_success()

    @command_group.command('list')
    @click.option('--full', is_flag=True)
    def datapushers_list(full):
        print(yaml.dump(list(full=full), default_flow_style=False))

    @command_group.command('get')
    @click.argument('DATAPUSHER_NAME')
    def datapushers_get(datapusher_name):
        print(yaml.dump(get(datapusher_name), default_flow_style=False))

    @command_group.command('delete')
    @click.argument('DATAPUSHER_NAME')
    def datapushers_delete(datapusher_name):
        delete(datapusher_name)
        great_success()


def initialize():
    install_crds()
    datapusher_envvars = {'PORT': '8000'}
    router_name = 'datapushers'
    if not routers_manager.get(router_name, required=False):
        routers_manager.create(router_name, routers_manager.get_traefik_router_spec())
    if config_manager.get('enable-deis-ckan', configmap_name='global-ckan-config') == 'y':
        create(
            'datapusher-1',
            'registry.gitlab.com/viderum/docker-datapusher:cloud-datapusher-1-v9',
            datapusher_envvars,
            router_name
        )
        create(
            'datapusher-de',
            'registry.gitlab.com/viderum/docker-datapusher:cloud-de-git-943fc3e0',
            datapusher_envvars,
            router_name
        )
        create(
            'datapusher-giga',
            'registry.gitlab.com/viderum/docker-datapusher:cloud-giga-git-2b05b22d',
            datapusher_envvars,
            router_name
        )
        create(
            'datapusher-increased-max-length',
            'registry.gitlab.com/viderum/docker-datapusher:cloud-increased-max-length-git-84e86116',
            datapusher_envvars,
            router_name
        )
        update('datapusher-1')
        update('datapusher-de')
        update('datapusher-giga')
        update('datapusher-increased-max-length')
        routers_manager.update(router_name)


def install_crds():
    """Ensures installaion of the datapusher custom resource definitions on the cluster"""
    kubectl.install_crd('ckanclouddatapushers', 'ckanclouddatapusher', 'CkanCloudDatapusher')


def create(name, image, config, router_name=None):
    labels =  _get_labels(name)
    datapusher = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudDatapusher', name, labels)
    datapusher['spec'] = {'image': image,
                          'config': config}
    kubectl.apply(datapusher)
    if router_name:
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'datapusher',
            'datapusher-name': name
        })


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


def update_service(name, labels):
    labels.update(**_get_labels(name))
    service = kubectl.get_resource('v1', 'Service', get_service_name(name), labels)
    service['spec'] = {
        'ports': [
            {'name': '8000', 'port': 8000}
        ],
        'selector': {
            'ckan-cloud/datapusher-name': name,
            'app': 'datapusher',
        }
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
                'labels': dict(labels, app='datapusher')
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
        print('Creating datapushers registry secret')
        from ckan_cloud_operator.providers.ckan import manager as ckan_manager
        docker_server, docker_username, docker_password, docker_email = ckan_manager.get_docker_credentials()
        kubectl.check_call(f'create secret docker-registry datapushers-docker-registry '
                           f'--docker-password={docker_password} '
                           f'--docker-server={docker_server} '
                           f'--docker-username={docker_username} '
                           f'--docker-email={docker_email}')
