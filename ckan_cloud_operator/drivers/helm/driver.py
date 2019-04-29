import subprocess

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs


def init(tiller_namespace_name):
    if kubectl.get('ns', tiller_namespace_name, required=False):
        logs.info('namespace already exists')
    else:
        subprocess.check_call(['kubectl', 'create', 'namespace', tiller_namespace_name])
    tiller_service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": f"{tiller_namespace_name}-tiller",
            "namespace": tiller_namespace_name
        }
    }
    cluster_role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {
          "name": f"{tiller_namespace_name}-tiller"
        },
        "roleRef": {
          "apiGroup": "rbac.authorization.k8s.io",
          "kind": "ClusterRole",
          "name": "cluster-admin"
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": f"{tiller_namespace_name}-tiller",
                "namespace": tiller_namespace_name
            }
        ]
    }
    kubectl.apply(tiller_service_account)
    kubectl.apply(cluster_role_binding)
    subprocess.check_call(
        f'helm init --upgrade --service-account {tiller_namespace_name}-tiller --tiller-namespace {tiller_namespace_name} --history-max 10',
        shell=True
    )


def deploy(tiller_namespace, chart_repo, chart_name, chart_version, release_name, values_filename, namespace):
    subprocess.check_call(f'helm repo add ckan-cloud "{chart_repo}"', shell=True)
    version_args = f'--version "{chart_version}"' if chart_version else ''
    dry_run_args = '--dry-run --debug'
    cmd = f'helm --tiller-namespace {tiller_namespace} upgrade {release_name} {chart_name} ' \
          f' --install --namespace "{namespace}" -if {values_filename} {version_args}'
    subprocess.check_call(f'{cmd} {dry_run_args}', shell=True)
    subprocess.check_call(cmd, shell=True)
