import subprocess
import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import gcloud


ROLES = {
    'admin': {},
    'manager': {}
}


def create(name, role):
    print(f'Creating CkanCloudUser {name} (role={role})')
    assert role in ROLES
    labels =  {'ckan-cloud/user-role': role}
    router = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudUser', name, labels)
    router['spec'] = {'role': role}
    kubectl.create(router)


def _update_admin_role_user(name, service_account_name, role, labels):
    kubectl.apply({
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {
            "name": f'ckan-cloud-admin',
            'labels': labels
        },
        "rules": [
            {
                "apiGroups": [
                    "*"
                ],
                "resources": [
                    "*"
                ],
                "verbs": [
                    "*"
                ]
            },
            {
                "nonResourceURLs": [
                    "*"
                ],
                "verbs": [
                    "*"
                ]
            }
        ]
    }, reconcile=True)
    kubectl.apply({
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'ClusterRoleBinding',
        'metadata': {
            'name': f'ckan-cloud-{name}-{role}',
            'labels': labels
        },
        'subjects': [
            {
                'kind': 'User',
                'name': f'system:serviceaccount:ckan-cloud:{service_account_name}',
                'apiGroup': 'rbac.authorization.k8s.io'
            }
        ],
        'roleRef': {
            'kind': 'ClusterRole',
            'name': 'ckan-cloud-admin',
            'apiGroup': 'rbac.authorization.k8s.io'
        }
    }, reconcile=True)


def _delete_admin_role_user(name, role):
    kubectl.call(f'delete ClusterRoleBinding ckan-cloud-{name}-{role}')


def _update_namespaced_manager_role_user(name, service_account_name, role, labels, namespace='ckan-cloud'):
    kubectl.apply({
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": f'ckan-cloud-manager',
            'namespace': namespace,
            'labels': labels
        },
        "rules": [
            {
                "apiGroups": [
                    "*"
                ],
                "resources": [
                    "*"
                ],
                "verbs": [
                    "*"
                ]
            }
        ]
    }, reconcile=True)
    kubectl.apply({
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'RoleBinding',
        'metadata': {
            'name': f'ckan-cloud-{name}-{role}',
            'namespace': namespace,
            'labels': labels
        },
        'subjects': [
            {
                'kind': 'ServiceAccount',
                'name': service_account_name,
                'namespace': namespace,
            }
        ],
        'roleRef': {
            'kind': 'Role',
            'name': 'ckan-cloud-manager',
            'namespace': namespace,
            'apiGroup': 'rbac.authorization.k8s.io'
        }
    }, reconcile=True)


def _delete_namespaced_manager_role_user(name, role):
    kubectl.call(f'delete RoleBinding ckan-cloud-{name}-{role}')


def _update_user(name, role):
    assert role in ROLES
    labels = {'ckan-cloud/user-role': role,
              'ckan-cloud/user-name': name}
    service_account_name = f'ckan-cloud-user-{name}'
    kubectl.apply(kubectl.get_resource('v1', 'ServiceAccount', service_account_name, labels))
    if role == 'admin':
        _update_admin_role_user(name, service_account_name, role, labels)
    elif role == 'manager':
        _update_namespaced_manager_role_user(name, service_account_name, role, labels)
    else:
        raise NotImplementedError(f'unsupported role: {role}')


def delete(name):
    user = kubectl.get(f'CkanCloudUser {name}')
    spec = user['spec']
    role = spec['role']
    assert role in ROLES
    if role == 'admin':
        _delete_admin_role_user(name, role)
    elif role == 'manager':
        _delete_namespaced_manager_role_user(name, role)
    else:
        raise NotImplementedError(f'unsupported role: {role}')
    kubectl.call(f'delete ServiceAccount ckan-cloud-user-{name}')


def get(name):
    service_account_name = f'ckan-cloud-user-{name}'
    service_account = kubectl.get(f'ServiceAccount {service_account_name}')
    secret_name = service_account['secrets'][0]['name']
    secret = kubectl.decode_secret(kubectl.get(f'secret {secret_name}'))
    ckan_infra = CkanInfra()
    cluster_name = ckan_infra.GCLOUD_CLUSTER_NAME
    cluster = yaml.load(gcloud.check_output(f'container clusters describe {cluster_name}',
                                            ckan_infra=ckan_infra))
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "users": [
            {
                "name": service_account_name,
                "user": {
                    "token": secret['token']
                }
            }
        ],
        "clusters": [
            {
                "name": cluster_name,
                "cluster": {
                    "server": 'https://' + cluster['endpoint'],
                    "certificate-authority-data": cluster['masterAuth']['clusterCaCertificate']
                }
            }
        ],
        "contexts": [
            {
                "name": cluster_name,
                "context": {
                    "cluster": cluster_name,
                    "user": service_account_name
                }
            }
        ],
        "current-context": cluster_name
    }


def update(name):
    print(f'updating CkanCloudUser {name}')
    user = kubectl.get(f'CkanCloudUser {name}')
    spec = user['spec']
    role = spec['role']
    assert role in ROLES
    annotations = CkanUserAnnotations(name, user)
    annotations.update_status(
        'user', 'created',
        lambda: _update_user(name, role),
        force_update=True
    )


def install_crds():
    """Ensures installaion of the user custom resource definitions on the cluster"""
    kubectl.install_crd('ckancloudusers', 'ckanclouduser', 'CkanCloudUser')


class CkanUserAnnotations(kubectl.BaseAnnotations):
    """Manage user annotations"""

    @property
    def FLAGS(self):
        """Boolean flags which are saved as annotations on the resource"""
        return [
            'forceCreateAnnotations',
        ]

    @property
    def STATUSES(self):
        """Predefined statuses which are saved as annotations on the resource"""
        return {
            'user': ['created']
        }

    @property
    def SECRET_ANNOTATIONS(self):
        """Sensitive details which are saved in a secret related to the resource"""
        return []

    @property
    def RESOURCE_KIND(self):
        return 'CkanCloudUser'
