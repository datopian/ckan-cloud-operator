import subprocess
import yaml
import base64
import json
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.deis_ckan import datapusher
from ckan_cloud_operator.db import manager as db_manager


class DeisCkanInstanceEnvvars(object):

    def __init__(self, instance):
        self.instance = instance
        self.solr_spec = self.instance.spec.solrCloudCollection

    def _apply_instance_envvars_overrides(self, instance_envvars_secret):
        if 'overrides' in self.instance.spec.envvars:
            print('Applying instance envvars overrides')
            for k, v in self.instance.spec.envvars['overrides'].items():
                instance_envvars_secret['data'][k] = base64.b64encode(v.encode()).decode()

    def _update(self):
        spec = self.instance.spec
        ckan_infra = self.instance.ckan_infra
        db_name = spec.db['name']
        db_password = self.instance.annotations.get_secret('databasePassword')
        datastore_name = spec.datastore['name']
        datastore_password = self.instance.annotations.get_secret('datastorePassword')
        datastore_ro_user = self.instance.annotations.get_secret('datastoreReadonlyUser')
        datastore_ro_password = self.instance.annotations.get_secret('datatastoreReadonlyPassword')
        # solr_http_endpoint = ckan_infra.SOLR_HTTP_ENDPOINT_SIMPLE
        # a proxy solr to support authenticated requests for ckan 2.6, 2.7
        solr_http_endpoint = 'http://solrcloud-proxy.ckan-cloud:8983/solr'
        solr_collection_name = spec.solrCloudCollection['name']
        if 'fromSecret' in spec.envvars:
            envvars = kubectl.get(f'secret {spec.envvars["fromSecret"]}')
            envvars = yaml.load(kubectl.decode_secret(envvars, 'envvars.yaml'))
        elif 'fromGitlab' in spec.envvars:
            envvars = CkanGitlab(self.instance.ckan_infra).get_envvars(spec.envvars['fromGitlab'])
        else:
            raise Exception(f'invalid envvars spec: {spec.envvars}')
        assert envvars['CKAN_SITE_ID'] and envvars['CKAN_SITE_URL'] and envvars['CKAN_SQLALCHEMY_URL']
        minio_secret = kubectl.decode_secret(kubectl.get('secret minio-credentials'))
        storage_path_parts = spec.storage['path'].strip('/').split('/')
        storage_bucket = storage_path_parts[0]
        storage_path = '/'.join(storage_path_parts[1:])
        postgres_host, postgres_port = db_manager.get_internal_proxy_host_port()
        envvars.update(
            CKAN_SQLALCHEMY_URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:{postgres_port}/{db_name}",
            CKAN___BEAKER__SESSION__URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:{postgres_port}/{db_name}",
            CKAN__DATASTORE__READ_URL=f"postgresql://{datastore_ro_user}:{datastore_ro_password}@{postgres_host}:5432/{datastore_name}",
            CKAN__DATASTORE__WRITE_URL=f"postgresql://{datastore_name}:{datastore_password}@{postgres_host}:5432/{datastore_name}",
            CKAN_SOLR_URL=f"{solr_http_endpoint}/{solr_collection_name}",
            # we are using the non-authenticated proxy, so this has to be disabled to prevent ckans which support auth from using them
            # CKAN_SOLR_USER=ckan_infra.SOLR_USER,
            # CKAN_SOLR_PASSWORD=ckan_infra.SOLR_PASSWORD,
            CKANEXT__S3FILESTORE__AWS_STORAGE_PATH=storage_path,
            CKANEXT__S3FILESTORE__AWS_ACCESS_KEY_ID=minio_secret['MINIO_ACCESS_KEY'],
            CKANEXT__S3FILESTORE__AWS_SECRET_ACCESS_KEY=minio_secret['MINIO_SECRET_KEY'],
            CKANEXT__S3FILESTORE__AWS_BUCKET_NAME=storage_bucket,
            CKANEXT__S3FILESTORE__HOST_NAME=f'https://cc-{ckan_infra.ROUTERS_ENV_ID}-minio.{ckan_infra.ROUTERS_DEFAULT_ROOT_DOMAIN}/',
            CKANEXT__S3FILESTORE__REGION_NAME='us-east-1',
            CKANEXT__S3FILESTORE__SIGNATURE_VERSION='s3v4',
            CKAN__DATAPUSHER__URL=datapusher.get_datapusher_url(envvars.get('CKAN__DATAPUSHER__URL')),
        )
        # print(yaml.dump(envvars, default_flow_style=False))
        instance_envvars_secret = {'apiVersion': 'v1',
                                   'kind': 'Secret',
                                   'metadata': {
                                       'name': 'ckan-envvars',
                                       'namespace': self.instance.id
                                   },
                                   'type': 'Opaque',
                                   'data': {k: base64.b64encode(v.encode() if v else b'').decode()
                                            for k, v in envvars.items()}}
        self._apply_instance_envvars_overrides(instance_envvars_secret)
        subprocess.run('kubectl apply -f -', input=yaml.dump(instance_envvars_secret).encode(),
                       shell=True, check=True)

    def update(self):
        if not self.instance.annotations.update_status('envvars', 'created', lambda: self._update()):
            self._update()

    def delete(self):
        print('Deleting instance envvars secret')
        subprocess.check_call(f'kubectl -n {self.instance.id} delete secret/ckan-envvars', shell=True)

    def get(self):
        exitcode, output = subprocess.getstatusoutput(f'kubectl -n {self.instance.id} get secret/ckan-envvars -o yaml')
        if exitcode == 0:
            secret = kubectl.decode_secret(yaml.load(output))
            return {'ready': 'CKAN_SITE_URL' in secret}
        else:
            return {'ready': False, 'error': output}
