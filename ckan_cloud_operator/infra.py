import subprocess
import yaml
import base64
from ckan_cloud_operator import kubectl


class CkanInfra(object):

    def __init__(self):
        values = kubectl.decode_secret(kubectl.get('secret ckan-infra'))
        self.GCLOUD_SQL_INSTANCE_NAME = values.get('GCLOUD_SQL_INSTANCE_NAME')
        self.GCLOUD_SQL_PROJECT = values.get('GCLOUD_SQL_PROJECT')
        self.POSTGRES_HOST = values.get('POSTGRES_HOST')
        self.POSTGRES_USER = values.get('POSTGRES_USER')
        self.POSTGRES_PASSWORD = values.get('POSTGRES_PASSWORD')
        self.SOLR_HTTP_ENDPOINT = values.get('SOLR_HTTP_ENDPOINT')
        self.SOLR_NUM_SHARDS = values.get('SOLR_NUM_SHARDS')
        self.SOLR_REPLICATION_FACTOR = values.get('SOLR_REPLICATION_FACTOR')
        self.DOCKER_REGISTRY_SERVER = values.get('DOCKER_REGISTRY_SERVER')
        self.DOCKER_REGISTRY_USERNAME = values.get('DOCKER_REGISTRY_USERNAME')
        self.DOCKER_REGISTRY_PASSWORD = values.get('DOCKER_REGISTRY_PASSWORD')
        self.DOCKER_REGISTRY_EMAIL = values.get('DOCKER_REGISTRY_EMAIL')
        self.GITLAB_TOKEN_USER = values.get('GITLAB_TOKEN_USER')
        self.GITLAB_TOKEN_PASSWORD = values.get('GITLAB_TOKEN_PASSWORD')
        self.DEIS_KUBECONFIG = values.get('DEIS_KUBECONFIG')
        self.GCLOUD_SERVICE_ACCOUNT_JSON = values.get('GCLOUD_SERVICE_ACCOUNT_JSON')
        self.GCLOUD_SERVICE_ACCOUNT_EMAIL = values.get('GCLOUD_SERVICE_ACCOUNT_EMAIL')
        self.GCLOUD_AUTH_PROJECT = values.get('GCLOUD_AUTH_PROJECT')
        self.MULTI_USER_STORAGE_CLASS_NAME = values.get('MULTI_USER_STORAGE_CLASS_NAME', 'cca-ckan')
        self.GCLOUD_CLUSTER_NAME = values.get('GCLOUD_CLUSTER_NAME')
        self.GCLOUD_STORAGE_BUCKET = values.get('GCLOUD_STORAGE_BUCKET')
        self.GCLOUD_STORAGE_ACCESS_KEY_ID = values.get('GCLOUD_STORAGE_ACCESS_KEY_ID')
        self.GCLOUD_STORAGE_SECRET_ACCESS_KEY = values.get('GCLOUD_STORAGE_SECRET_ACCESS_KEY')
        self.GCLOUD_STORAGE_HOST_NAME = values.get('GCLOUD_STORAGE_HOST_NAME')
        self.GCLOUD_STORAGE_REGION_NAME = values.get('GCLOUD_STORAGE_REGION_NAME')
        self.GCLOUD_STORAGE_SIGNATURE_VERSION = values.get('GCLOUD_STORAGE_SIGNATURE_VERSION')
        self.ROUTERS_ENV_ID = values.get('ROUTERS_ENV_ID')

    @classmethod
    def set(cls, set_type, *args):
        print(f'Setting {set_type} infra secrets')
        if set_type == 'gcloud':
            service_account_json, service_account_email, auth_project = args
            with open(service_account_json, 'rb') as f:
                kubectl.update_secret('ckan-infra',
                                      {'GCLOUD_SERVICE_ACCOUNT_JSON': f.read().decode(),
                                       'GCLOUD_SERVICE_ACCOUNT_EMAIL': service_account_email,
                                       'GCLOUD_AUTH_PROJECT': auth_project})
        if set_type == 'docker-registry':
            server, username, password, email = args
            kubectl.update_secret('ckan-infra',
                                  {'DOCKER_REGISTRY_SERVER': server,
                                   'DOCKER_REGISTRY_USERNAME': username,
                                   'DOCKER_REGISTRY_PASSWORD': password,
                                   'DOCKER_REGISTRY_EMAIL': email})

        else:
            raise NotImplementedError(f'Invalid infra set spec: {set_type}={args}')

    @classmethod
    def clone(cls, other_secret):
        secret = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': 'ckan-infra',
                'namespace': 'ckan-cloud'
            },
            'type': 'Opaque',
            'data': other_secret['data']
        }
        subprocess.run('kubectl create -f -', input=yaml.dump(secret).encode(),
                       shell=True, check=True)

    @classmethod
    def get(cls):
        secret = kubectl.get('secret ckan-infra', required=False)
        if secret:
            return kubectl.decode_secret(secret)
        else:
            return {}
