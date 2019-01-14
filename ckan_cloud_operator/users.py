from ckan_cloud_operator import kubectl


ROLES = {
    'admin': {}
}


def create(name, role):
    print(f'Creating CkanCloudUser {name} (role={role})')
    assert role in ROLES
    labels =  {'ckan-cloud/user-role': role}
    router = kubectl.get_resource('stable.viderum.com/v1', 'CkanCloudUser', name, labels)
    router['spec'] = {'role': role}
    kubectl.create(router)


def _update_user(name, role, spec, annotations):
    print(name)
    print(role)
    raise Exception()


def update(name):
    print(f'updating CkanCloudUser {name}')
    user = kubectl.get(f'CkanCloudUser {name}')
    spec = user['spec']
    role = spec['role']
    assert role in ROLES
    annotations = CkanUserAnnotations(name, role)
    annotations.update_status(
        'user', 'created',
        lambda: _update_user(name, role, spec, annotations),
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
