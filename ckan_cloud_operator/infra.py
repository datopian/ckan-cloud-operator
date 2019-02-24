import subprocess
import yaml
import sys
import datetime
from urllib.parse import urlparse
import os

from ckan_cloud_operator import kubectl


class CkanInfra(object):

    @classmethod
    def add_cli_commands(cls, click, command_group, great_success):

        @command_group.command('clone')
        def __ckan_infra_clone():
            """Clone the infrastructure secret from an existing secret piped on stdin

            Example: KUBECONFIG=/other/.kube-config kubectl -n ckan-cloud get secret ckan-infra -o yaml | ckan-cloud-operator ckan-infra clone
            """
            cls.clone(yaml.load(sys.stdin.read()))
            great_success()

        @command_group.group('set')
        def __ckan_infra_set():
            """Set or overwrite infrastructure secrets"""
            pass

        @__ckan_infra_set.command('key-value')
        @click.argument('KEY')
        @click.argument('VALUE')
        def ckan_infra_set_key_value(key, value):
            """Sets an arbitrary key/value pair on the ckan-infra secret. Use --force to overwrite existing values"""
            cls.set('key-value', key, value)
            great_success()


        @__ckan_infra_set.command('gcloud')
        @click.argument('GCLOUD_SERVICE_ACCOUNT_JSON_FILE')
        @click.argument('GCLOUD_SERVICE_ACCOUNT_EMAIL')
        @click.argument('GCLOUD_AUTH_PROJECT')
        def ckan_infra_set_gcloud(gcloud_service_account_json_file, gcloud_service_account_email, gcloud_auth_project):
            """Sets the Google cloud authentication details, should run locally or mount the json file into the container"""
            cls.set('gcloud', gcloud_service_account_json_file, gcloud_service_account_email, gcloud_auth_project)
            great_success()

        @__ckan_infra_set.command('docker-registry')
        @click.argument('DOCKER_REGISTRY_SERVER')
        @click.argument('DOCKER_REGISTRY_USERNAME')
        @click.argument('DOCKER_REGISTRY_PASSWORD')
        @click.argument('DOCKER_REGISTRY_EMAIL')
        def ckan_infra_set_docker_registry(docker_registry_server, docker_registry_username, docker_registry_password,
                                           docker_registry_email):
            """Sets the Docker registry details for getting private images for CKAN pods in the cluster"""
            cls.set('docker-registry',
                    docker_registry_server, docker_registry_username, docker_registry_password, docker_registry_email)
            great_success()

        @command_group.command('get')
        @click.argument('CKAN_INFRA_KEY', required=False)
        def ckan_infra_get(ckan_infra_key):
            """Get the ckan-infra secrets"""
            if ckan_infra_key:
                print(getattr(cls(), ckan_infra_key))
            else:
                print(yaml.dump(cls.get(), default_flow_style=False))

        @command_group.command('admin-db-connection-string')
        def ckan_infra_admin_db_connection_string():
            """Get a DB connection string for administration

            Example: psql -d $(ckan-cloud-operator admin-db-connection-string)
            """
            infra = cls()
            postgres_user = infra.POSTGRES_USER
            postgres_password = infra.POSTGRES_PASSWORD
            if os.environ.get('CKAN_CLOUD_OPERATOR_USE_PROXY') in ['yes', '1', 'true']:
                postgres_host = '127.0.0.1'
            else:
                postgres_host = infra.POSTGRES_HOST
            postgres_port = '5432'
            print(f'postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}')

        @command_group.command('cloudsql-proxy')
        def ckan_infra_cloudsql_proxy():
            """Starts a local proxy to the cloud SQL instance"""
            print("Keep this running in the background")
            print("Set the following environment variable to cause ckan-cloud-operator to connect via the proxy")
            print("export CKAN_CLOUD_OPERATOR_USE_PROXY=yes")
            subprocess.check_call(f'kubectl -n ckan-cloud port-forward deployment/ckan-cloud-db-proxy-pgbouncer 5432', shell=True)

        @command_group.command('deploy-solr-proxy')
        def deploy_ckan_infra_solr_proxy():
            """Deploys a proxy inside the cluster which allows to access the centralized solr without authentication"""
            labels = {'app': 'ckan-cloud-solrcloud-proxy'}
            infra = cls()
            solr_url = urlparse(infra.SOLR_HTTP_ENDPOINT)
            scheme = solr_url.scheme
            hostname = solr_url.hostname
            port = solr_url.port
            if not port:
                port = '443' if scheme == 'https' else '8983'
            kubectl.update_secret('solrcloud-proxy', {
                'SOLR_URL': f'{scheme}://{hostname}:{port}',
                'SOLR_USER': infra.SOLR_USER,
                'SOLR_PASSWORD': infra.SOLR_PASSWORD
            })
            kubectl.apply(kubectl.get_deployment('solrcloud-proxy', labels, {
                'replicas': 1,
                'revisionHistoryLimit': 10,
                'strategy': {'type': 'RollingUpdate', },
                'template': {
                    'metadata': {
                        'labels': labels,
                        'annotations': {
                            'ckan-cloud/operator-timestamp': str(datetime.datetime.now())
                        }
                    },
                    'spec': {
                        'containers': [
                            {
                                'name': 'solrcloud-proxy',
                                'image': 'viderum/ckan-cloud-operator-solrcloud-proxy',
                                'envFrom': [{'secretRef': {'name': 'solrcloud-proxy'}}],
                                'ports': [{'containerPort': 8983}],
                            }
                        ]
                    }
                }
            }))
            service = kubectl.get_resource('v1', 'Service', 'solrcloud-proxy', labels)
            service['spec'] = {
                'ports': [
                    {'name': '8983', 'port': 8983}
                ],
                'selector': labels
            }
            kubectl.apply(service)

    def __init__(self, required=True):
        if required:
            values = kubectl.decode_secret(kubectl.get('secret ckan-infra', required=required), required=required)
        else:
            values = {}

        # Database

        self.POSTGRES_HOST = values.get('POSTGRES_HOST')
        self.POSTGRES_USER = values.get('POSTGRES_USER')
        self.POSTGRES_PASSWORD = values.get('POSTGRES_PASSWORD')
        self.GCLOUD_SQL_INSTANCE_NAME = values.get('GCLOUD_SQL_INSTANCE_NAME')
        self.GCLOUD_SQL_PROJECT = values.get('GCLOUD_SQL_PROJECT')

        # Solr

        self.SOLR_HTTP_ENDPOINT = values.get('SOLR_HTTP_ENDPOINT')
        self.SOLR_HTTP_ENDPOINT_SIMPLE = values.get('SOLR_HTTP_ENDPOINT_SIMPLE')
        self.SOLR_USER = values.get('SOLR_USER')
        self.SOLR_PASSWORD = values.get('SOLR_PASSWORD')
        self.SOLR_NUM_SHARDS = values.get('SOLR_NUM_SHARDS')
        self.SOLR_REPLICATION_FACTOR = values.get('SOLR_REPLICATION_FACTOR')

        # Private Docker Registry

        self.DOCKER_REGISTRY_SERVER = values.get('DOCKER_REGISTRY_SERVER')
        self.DOCKER_REGISTRY_USERNAME = values.get('DOCKER_REGISTRY_USERNAME')
        self.DOCKER_REGISTRY_PASSWORD = values.get('DOCKER_REGISTRY_PASSWORD')
        self.DOCKER_REGISTRY_EMAIL = values.get('DOCKER_REGISTRY_EMAIL')

        # GitLab

        self.GITLAB_TOKEN_USER = values.get('GITLAB_TOKEN_USER')
        self.GITLAB_TOKEN_PASSWORD = values.get('GITLAB_TOKEN_PASSWORD')

        # Migration from old cluster

        self.DEIS_KUBECONFIG = values.get('DEIS_KUBECONFIG')
        self.GCLOUD_SQL_DEIS_IMPORT_BUCKET = values.get('GCLOUD_SQL_DEIS_IMPORT_BUCKET')

        # Gcloud credentials / general details

        self.GCLOUD_SERVICE_ACCOUNT_JSON = values.get('GCLOUD_SERVICE_ACCOUNT_JSON')
        self.GCLOUD_SERVICE_ACCOUNT_EMAIL = values.get('GCLOUD_SERVICE_ACCOUNT_EMAIL')
        self.GCLOUD_AUTH_PROJECT = values.get('GCLOUD_AUTH_PROJECT')
        self.GCLOUD_COMPUTE_ZONE = values.get('GCLOUD_COMPUTE_ZONE')
        self.GCLOUD_CLUSTER_NAME = values.get('GCLOUD_CLUSTER_NAME')

        # Gcloud Storage

        self.GCLOUD_STORAGE_BUCKET = values.get('GCLOUD_STORAGE_BUCKET')
        self.GCLOUD_STORAGE_ACCESS_KEY_ID = values.get('GCLOUD_STORAGE_ACCESS_KEY_ID')
        self.GCLOUD_STORAGE_SECRET_ACCESS_KEY = values.get('GCLOUD_STORAGE_SECRET_ACCESS_KEY')
        self.GCLOUD_STORAGE_HOST_NAME = values.get('GCLOUD_STORAGE_HOST_NAME')
        self.GCLOUD_STORAGE_REGION_NAME = values.get('GCLOUD_STORAGE_REGION_NAME')
        self.GCLOUD_STORAGE_SIGNATURE_VERSION = values.get('GCLOUD_STORAGE_SIGNATURE_VERSION')

        # Cluster Storage

        self.MULTI_USER_STORAGE_CLASS_NAME = values.get('MULTI_USER_STORAGE_CLASS_NAME', 'cca-ckan')

        # Routers / Load Balancing

        self.ROUTERS_ENV_ID = values.get('ROUTERS_ENV_ID')
        self.ROUTERS_DEFAULT_ROOT_DOMAIN = values.get('ROUTERS_DEFAULT_ROOT_DOMAIN')
        self.ROUTERS_DEFAULT_CLOUDFLARE_EMAIL = values.get('ROUTERS_DEFAULT_CLOUDFLARE_EMAIL')
        self.ROUTERS_DEFAULT_CLOUDFLARE_AUTH_KEY = values.get('ROUTERS_DEFAULT_CLOUDFLARE_AUTH_KEY')

        # Monitoring
        self.CKAN_STATUSCAKE_API_KEY = values.get('CKAN_STATUSCAKE_API_KEY')
        self.CKAN_STATUSCAKE_API_USER = values.get('CKAN_STATUSCAKE_API_USER')
        self.CKAN_STATUSCAKE_GROUP = values.get('CKAN_STATUSCAKE_GROUP')

    @classmethod
    def set(cls, set_type, *args):
        print(f'Setting {set_type} infra secrets')
        if set_type == 'key-value':
            key, value = args
            kubectl.update_secret('ckan-infra', {key: value})
        elif set_type == 'gcloud':
            service_account_json, service_account_email, auth_project = args
            with open(service_account_json, 'rb') as f:
                kubectl.update_secret('ckan-infra',
                                      {'GCLOUD_SERVICE_ACCOUNT_JSON': f.read().decode(),
                                       'GCLOUD_SERVICE_ACCOUNT_EMAIL': service_account_email,
                                       'GCLOUD_AUTH_PROJECT': auth_project})
        elif set_type == 'docker-registry':
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
