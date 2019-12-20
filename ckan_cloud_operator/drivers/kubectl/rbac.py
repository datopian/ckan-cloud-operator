from ckan_cloud_operator import kubectl


def update_service_account(service_account_name, labels, namespace=None):
    service_account = kubectl.get_resource(
        'v1', 'ServiceAccount', service_account_name, labels
    )
    if namespace:
        service_account['metadata']['namespace'] = namespace
    kubectl.apply(service_account)


def update_cluster_role(name, rules, labels):
    kubectl.apply({
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {
            "name": name,
            'labels': labels
        },
        "rules": rules
    }, reconcile=True)


def update_admin_cluster_role(name, labels):
    update_cluster_role(name, [
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
    ], labels)


def update_cluster_role_binding(name, subject,
                                cluster_role_name, labels):
    resource = {
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'ClusterRoleBinding',
        'metadata': {
            'name': name,
            'labels': labels
        },
        'subjects': [subject],
        'roleRef': {
            'kind': 'ClusterRole',
            'name': cluster_role_name,
            'apiGroup': 'rbac.authorization.k8s.io'
        }
    }
    kubectl.apply(resource, reconcile=True)


def update_role(name, labels, rules, namespace):
    kubectl.apply({
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": name,
            'namespace': namespace,
            'labels': labels
        },
        "rules": rules
    }, reconcile=True)


def update_role_binding(name, role_name, namespace, service_account_name, labels):
    kubectl.apply({
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'RoleBinding',
        'metadata': {
            'name': name,
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
            'name': role_name,
            'namespace': namespace,
            'apiGroup': 'rbac.authorization.k8s.io'
        }
    }, reconcile=True)


def get_kubeconfig(cluster_name, service_account_namespace, service_account_name, cluster_spec=None):
    service_account = kubectl.get(f'ServiceAccount {service_account_name}', namespace=service_account_namespace)
    secret_name = service_account['secrets'][0]['name']
    secret = kubectl.decode_secret(kubectl.get(f'secret {secret_name}', namespace=service_account_namespace))
    config = kubectl.get('config view', get_cmd='')
    assert len(config['clusters']) == 1
    if not cluster_spec:
        cluster_spec = {"server": config['clusters'][0]['cluster']['server']}
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
                "cluster": cluster_spec
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