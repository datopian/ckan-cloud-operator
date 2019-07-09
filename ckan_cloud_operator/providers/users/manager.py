from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs

from ckan_cloud_operator.providers import manager as providers_manager
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager

from ckan_cloud_operator.providers.users.constants import PROVIDER_SUBMODULE as users_provider_submodule
from .constants import CRD_KIND, CRD_PLURAL, CRD_SINGULAR


def initialize(default_provider=None, interactive=False):
    crds_manager.install_crd(CRD_SINGULAR, CRD_PLURAL, CRD_KIND)
    if not default_provider:
        default_provider = 'gcloud' if cluster_manager.get_provider_id() == 'gcloud' else 'rancher'
    providers_manager.get_provider(users_provider_submodule, required=False, default=default_provider).initialize(interactive=interactive)


def create(name, role):
    logs.info(f'Creating user {name} (role={role})')
    try:
        extra_label_suffixes = get_user_labels(name, role)
    except AssertionError:
        logs.info('No user labels found, initializing and retrying')
        initialize()
        extra_label_suffixes = get_user_labels(name, role)

    kubectl.apply(crds_manager.get_resource(
        CRD_SINGULAR,
        name,
        spec=_get_spec(name, role),
        extra_label_suffixes=extra_label_suffixes
    ))


def update(name):
    logs.info(f'Updating user: {name}')
    providers_manager.get_provider(users_provider_submodule, verbose=True).update(get(name))


def get(name):
    return crds_manager.get(CRD_SINGULAR, name=name)


def get_kubeconfig(name):
    return _get_provider().get_kubeconfig(get(name))


def get_user_labels(name, role):
    return {'name': name, 'role': role}


def get_role_labels(role):
    return {'role': role}


def _get_spec(name, role):
    return {'name': name, 'role': role}


def _get_provider(verbose=False):
    return providers_manager.get_provider(users_provider_submodule, verbose=verbose)
