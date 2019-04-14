#### standard provider code ####

from .constants import PROVIDER_ID
from ..constants import PROVIDER_SUBMODULE

# define common provider functions based on the constants
from ckan_cloud_operator.providers import manager as providers_manager
def _get_resource_name(suffix=None): return providers_manager.get_resource_name(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _get_resource_labels(for_deployment=False, suffix=None): return providers_manager.get_resource_labels(PROVIDER_SUBMODULE, PROVIDER_ID, for_deployment=for_deployment, suffix=suffix)
def _get_resource_annotations(suffix=None): return providers_manager.get_resource_annotations(PROVIDER_SUBMODULE, PROVIDER_ID, suffix=suffix)
def _set_provider(): providers_manager.set_provider(PROVIDER_SUBMODULE, PROVIDER_ID)
def _config_set(key=None, value=None, values=None, namespace=None, is_secret=False, suffix=None): providers_manager.config_set(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, value=value, values=values, namespace=namespace, is_secret=is_secret, suffix=suffix)
def _config_get(key=None, default=None, required=False, namespace=None, is_secret=False, suffix=None, template=None): return providers_manager.config_get(PROVIDER_SUBMODULE, PROVIDER_ID, key=key, default=default, required=required, namespace=namespace, is_secret=is_secret, suffix=suffix, template=template)
def _config_interactive_set(default_values, namespace=None, is_secret=False, suffix=None, from_file=False, interactive=False): providers_manager.config_interactive_set(PROVIDER_SUBMODULE, PROVIDER_ID, default_values, namespace, is_secret, suffix, from_file, interactive)


################################
# custom provider code starts here
#

import os
import binascii
import yaml
from ckan_cloud_operator import logs
from ckan_cloud_operator.drivers.rancher import driver as rancher_driver
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def _generate_password(l):
    return binascii.hexlify(os.urandom(l)).decode()


def initialize(interactive=False):
    _set_provider()
    assert interactive, 'non-interactive initialization is not supported'
    logs.info('To use the Rancher driver, please set the api endpoint credentials')
    print('You can get the credentials from Rancher UI, login as an admin user')
    print('  > Click on your profile pic top right corner'
          '    > API & Keys > Add Key')
    print('After you add the key the api endpoint and keys will be displayed')
    print('api-endpoint: https://<RANCHER_DOMAIN>/v3')
    print('default-context: <RANCHER_CLUSTER_ID>:<RANCHER_PROJECT_ID>')
    _config_interactive_set({
        'api-endpoint': '',
        'access-key': '',
        'secret-key': '',
        'default-context': '',

    }, is_secret=True, interactive=interactive)


def update(user):
    assert user['spec']['role'] == 'admin', 'only admin role is supported'
    username = user['spec']['name']
    password = _generate_password(12)
    config = _config_get(is_secret=True)
    api_endpoint, access_key, secret = [config['api-endpoint'], config['access-key'], config['secret-key']]
    print('---- # Creating Rancher user')
    res = rancher_driver.create_user(api_endpoint, access_key, secret, username, password)
    user_id = res['id']
    assert len(res['principalIds']) == 1, 'invalid principalIds'
    user_principal_id = res['principalIds'][0]
    print(yaml.dump(res, default_flow_style=False))
    cluster_id, _ = _config_get('default-context', is_secret=True).split(':')
    print('---- # Creating admin role bindings')
    logs.print_yaml_dump(
        rancher_driver.create_cluster_role_template_binding(api_endpoint, access_key, secret, cluster_id, user_principal_id)
    )
    print('---')
    logs.print_yaml_dump(
        rancher_driver.create_global_role_binding(api_endpoint, access_key, secret, user_id)
    )
    print('---- # Creating user token')
    res = rancher_driver.login(api_endpoint, username, password)
    user_login_token = res['token']
    logs.print_yaml_dump(res)
    print('---')
    res = rancher_driver.create_user_token(api_endpoint, user_login_token, 'ckan-cloud-operator')
    token = res['token']
    logs.print_yaml_dump(res)
    _config_set(f'{username}-token', token, is_secret=True)
    print('\n\nckan-cloud-operator uses the token to login, if you require human access, keep the username/password, it will not be displayed again\n\n')
    print('username:', username)
    print('password:', password)
    print('\n\n')
    logs.exit_great_success()


def get_kubeconfig(user):
    config = _config_get(is_secret=True)
    cluster_id, _ = config['default-context'].split(':')
    cluster_name = cluster_manager.get_cluster_name()
    api_endpoint = config['api-endpoint']
    k8s_endpoint = api_endpoint.replace('/v3', f'/k8s/clusters/{cluster_id}')
    user_name = user['spec']['name']
    user_token = config[f'{user_name}-token']
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [
            {
                "name": cluster_name,
                "cluster": {
                    "server": k8s_endpoint,
                    "api-version": "v1",

                }
            }
        ],
        "users": [
            {
                "name": user_name,
                "user": {
                    "token": user_token
                }
            }
        ],
        "contexts": [
            {
                "name": cluster_name,
                "context": {
                    "user": user_name,
                    "cluster": cluster_name
                }
            }
        ],
        "current-context": cluster_name
    }
