#### standard provider code ####

# import the correct PROVIDER_SUBMODULE and PROVIDER_ID constants for your provider
from ckan_cloud_operator.providers.users.gcloud.constants import PROVIDER_ID
from ckan_cloud_operator.providers.users.constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None): providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix)

################################
# custom provider code starts here
#

from ckan_cloud_operator import kubectl

from ckan_cloud_operator.drivers.kubectl import rbac
from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.providers.users.constants import CRD_SINGULAR
from ckan_cloud_operator.providers.users.manager import get_user_labels, get_role_labels
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize(interactive=False):
    _set_provider()


def update(user):
    _update_service_account(user)
    _update_role_binding(user)


def get_kubeconfig(user):
    return rbac.get_kubeconfig(
        cluster_name=cluster_manager.get_cluster_name(),
        service_account_name=_get_user_resource_name(user),
        service_account_namespace=_get_user_resource_namespace(user),
        cluster_spec=cluster_manager.get_cluster_kubeconfig_spec()
    )


def _get_name_role(user):
    return user['spec']['name'], user['spec']['role']


def _get_user_resource_name(user):
    return user['metadata']['name']


def _get_role_resource_name(user):
    _, role = _get_name_role(user)
    return crds_manager.get_resource_name(CRD_SINGULAR, f'role-{role}')


def _get_user_role_resource_name(user):
    name, role = _get_name_role(user)
    return crds_manager.get_resource_name(CRD_SINGULAR, f'user-{name}-role-{role}')


def _get_user_resource_namespace(user):
    return user['metadata']['namespace']


def _get_user_resource_labels(user):
    name, role = _get_name_role(user)
    return crds_manager.get_resource_labels(
        CRD_SINGULAR, name,
        extra_label_suffixes=get_user_labels(name, role)
    )


def _get_role_resource_labels(user):
    _, role = _get_name_role(user)
    return crds_manager.get_resource_labels(
        CRD_SINGULAR, role,
        extra_label_suffixes=get_role_labels(role)
    )


def _update_service_account(user):
    rbac.update_service_account(
        service_account_name=_get_user_resource_name(user),
        labels=_get_user_resource_labels(user)
    )


def _update_role_binding(user):
    name, role = _get_name_role(user)
    if role == 'admin':
        rbac.update_admin_cluster_role(
            name=_get_role_resource_name(user),
            labels=_get_role_resource_labels(user),
        )
        rbac.update_cluster_role_binding(
            name=_get_user_role_resource_name(user),
            subject={
                'kind': 'User',
                'name': f'system:serviceaccount:{_get_user_resource_namespace(user)}:{_get_user_resource_name(user)}',
                'apiGroup': 'rbac.authorization.k8s.io'
            },
            cluster_role_name=_get_role_resource_name(user),
            labels=_get_user_resource_labels(user)
        )
    else:
        raise NotImplementedError(f'unsupported role: {role}')
