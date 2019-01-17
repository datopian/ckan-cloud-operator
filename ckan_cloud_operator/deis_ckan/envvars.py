import subprocess
import yaml
import base64
import json
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.deis_ckan import datapusher


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
        postgres_host = ckan_infra.POSTGRES_HOST
        datastore_name = spec.datastore['name']
        datastore_password = self.instance.annotations.get_secret('datastorePassword')
        datastore_ro_user = self.instance.annotations.get_secret('datastoreReadonlyUser')
        datastore_ro_password = self.instance.annotations.get_secret('datatastoreReadonlyPassword')
        solr_http_endpoint = ckan_infra.SOLR_HTTP_ENDPOINT
        solr_collection_name = spec.solrCloudCollection['name']
        if 'fromSecret' in spec.envvars:
            envvars = kubectl.get(f'secret {spec.envvars["fromSecret"]}')
            envvars = yaml.load(kubectl.decode_secret(envvars, 'envvars.yaml'))
        elif 'fromGitlab' in spec.envvars:
            envvars = CkanGitlab(self.instance.ckan_infra).get_envvars(spec.envvars['fromGitlab'])
        else:
            raise Exception(f'invalid envvars spec: {spec.envvars}')
        assert envvars['CKAN_SITE_ID'] and envvars['CKAN_SITE_URL'] and envvars['CKAN_SQLALCHEMY_URL']
        storage_bucket_name, *storage_path = spec.storage['path'].strip('/').split('/')
        storage_path = '/'.join(storage_path)
        envvars.update(
            CKAN_SQLALCHEMY_URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:5432/{db_name}",
            CKAN___BEAKER__SESSION__URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:5432/{db_name}",
            CKAN__DATASTORE__READ_URL=f"postgresql://{datastore_ro_user}:{datastore_ro_password}@{postgres_host}:5432/{datastore_name}",
            CKAN__DATASTORE__WRITE_URL=f"postgresql://{datastore_name}:{datastore_password}@{postgres_host}:5432/{datastore_name}",
            CKAN_SOLR_URL=f"{solr_http_endpoint}/{solr_collection_name}",
            CKANEXT__S3FILESTORE__AWS_STORAGE_PATH=storage_path,
            CKANEXT__S3FILESTORE__AWS_ACCESS_KEY_ID=ckan_infra.GCLOUD_STORAGE_ACCESS_KEY_ID,
            CKANEXT__S3FILESTORE__AWS_SECRET_ACCESS_KEY=ckan_infra.GCLOUD_STORAGE_SECRET_ACCESS_KEY,
            CKANEXT__S3FILESTORE__AWS_BUCKET_NAME=storage_bucket_name,
            CKANEXT__S3FILESTORE__HOST_NAME=f'https://{ckan_infra.GCLOUD_STORAGE_BUCKET}.{ckan_infra.GCLOUD_STORAGE_HOST_NAME}/',
            CKANEXT__S3FILESTORE__REGION_NAME=ckan_infra.GCLOUD_STORAGE_REGION_NAME,
            CKANEXT__S3FILESTORE__SIGNATURE_VERSION=ckan_infra.GCLOUD_STORAGE_SIGNATURE_VERSION,
            CKAN__DATAPUSHER__URL=datapusher.get_datapusher_url(envvars.get('CKAN__DATAPUSHER__URL')),
        )
        instance_envvars_secret = {'apiVersion': 'v1',
                                   'kind': 'Secret',
                                   'metadata': {
                                       'name': 'ckan-envvars',
                                       'namespace': self.instance.id
                                   },
                                   'type': 'Opaque',
                                   'data': {k: base64.b64encode(v.encode()).decode()
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
