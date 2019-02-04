import datetime

from ckan_cloud_operator import kubectl

from ckan_cloud_operator.providers.db_web_ui.constants import PROVIDER_SUBMODULE
from ckan_cloud_operator.providers.db_web_ui.adminer.constants import PROVIDER_ID
from ckan_cloud_operator.providers import service as providers_service
from ckan_cloud_operator.providers import labels as providers_labels


def initialize():
    update()


def update():
    _apply_deployment()


def web_ui():
    label_prefix = _get_label_prefix()
    kubectl.check_call(f'port-forward deployment/{label_prefix} 8080')


def _apply_deployment():
    deployment_labels = _get_labels(for_deployment=True)
    label_prefix = _get_label_prefix()
    kubectl.apply(kubectl.get_deployment(label_prefix, deployment_labels, {
        'replicas': 1,
        'revisionHistoryLimit': 2,
        'strategy': {'type': 'RollingUpdate', },
        'template': {
            'metadata': {
                'labels': deployment_labels,
                'annotations': {
                    'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                }
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
    }))


def _set_provider():
    providers_service.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)


def _get_label_prefix():
    return providers_labels.get_provider_label_prefix(PROVIDER_SUBMODULE, PROVIDER_ID)


def _get_labels(for_deployment=False):
    return providers_labels.get_provider_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
