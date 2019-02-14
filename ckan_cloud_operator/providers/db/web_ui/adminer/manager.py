#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from ..constants import PROVIDER_SUBMODULE
from .constants import PROVIDER_ID

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)

################################

# custom provider code starts here
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.providers.db import manager as db_manager


def initialize():
    update()
    _set_provider()


def update():
    _apply_deployment()


def start():
    print('\n'.join([
        '',
        '\nadmin db credentials:\n' + str(db_manager.get_admin_db_credentials()),
        '\ninternal proxy host / port:\n' + str(db_manager.get_internal_proxy_host_port()),
        '\ninternal unproxied host / port:\n' + str(db_manager.get_internal_unproxied_db_host_port()),
        '\n'
    ]))
    deployment_name = _get_resource_name()
    kubectl.check_call(f'port-forward deployment/{deployment_name} 8080')


def _apply_deployment():
    deployment_name = _get_resource_name()
    deployment_labels = _get_resource_labels(for_deployment=True)
    deployment_annotations = _get_resource_annotations()
    kubectl.apply(kubectl.get_deployment(
        deployment_name,
        deployment_labels,
        {
            'replicas': 1,
            'revisionHistoryLimit': 2,
            'strategy': {'type': 'RollingUpdate', },
            'template': {
                'metadata': {
                    'labels': deployment_labels,
                    'annotations': deployment_annotations,
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'adminer',
                            'image': 'adminer',
                            'ports': [{'containerPort': 8080}],
                        }
                    ],
                }
            }
        }
    ))
