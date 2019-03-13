import subprocess
import yaml
from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.deis_ckan import datapusher
from ckan_cloud_operator.providers.db import manager as db_manager


class DeisCkanInstanceEnvvars(object):

    def __init__(self, instance):
        self.instance = instance
        self.solr_spec = self.instance.spec.solrCloudCollection
        self.site_url = None

    def _apply_instance_envvars_overrides(self, envvars):
        if 'overrides' in self.instance.spec.envvars:
            print('Applying instance envvars overrides')
            envvars.update(**self.instance.spec.envvars['overrides'])

    def _update(self):
        spec = self.instance.spec
        db_name = spec.db['name']
        db_password = self.instance.annotations.get_secret('databasePassword')
        datastore_name = spec.datastore['name']
        datastore_password = self.instance.annotations.get_secret('datastorePassword')
        datastore_ro_user = self.instance.annotations.get_secret('datastoreReadonlyUser')
        datastore_ro_password = self.instance.annotations.get_secret('datatastoreReadonlyPassword')
        no_db_proxy = True
        # db_no_db_proxy = spec.db.get('no-db-proxy') == 'yes'
        # datastore_no_db_proxy = spec.datastore.get('no-db-proxy') == 'yes'
        # if db_no_db_proxy or datastore_no_db_proxy:
        #     assert db_no_db_proxy and datastore_no_db_proxy, 'must set both DB and datastore with no-db-proxy'
        #     no_db_proxy = True
        # else:
        #     no_db_proxy = False
        from ckan_cloud_operator.providers.solr import manager as solr_manager
        solr_http_endpoint = solr_manager.get_internal_http_endpoint()
        solr_collection_name = spec.solrCloudCollection['name']
        if 'fromSecret' in spec.envvars:
            envvars = kubectl.get(f'secret {spec.envvars["fromSecret"]}')
            envvars = yaml.load(kubectl.decode_secret(envvars, 'envvars.yaml'))
        elif 'fromGitlab' in spec.envvars:
            envvars = CkanGitlab().get_envvars(spec.envvars['fromGitlab'])
        else:
            raise Exception(f'invalid envvars spec: {spec.envvars}')
        from ckan_cloud_operator.providers.storage import manager as storage_manager
        storage_hostname, storage_access_key, storage_secret_key = storage_manager.get_provider().get_credentials()
        storage_path_parts = spec.storage['path'].strip('/').split('/')
        storage_bucket = storage_path_parts[0]
        storage_path = '/'.join(storage_path_parts[1:])
        if no_db_proxy:
            postgres_host, postgres_port = db_manager.get_internal_unproxied_db_host_port(db_prefix=spec.db.get('dbPrefix') or '')
            logs.info(f'Bypassing db proxy, connecting to DB directly: {postgres_host}:{postgres_port}')
        else:
            postgres_host, postgres_port = db_manager.get_internal_proxy_host_port()
            logs.info(f'Connecting to DB proxy: {postgres_host}:{postgres_port}')
        envvars.update(
            CKAN_SQLALCHEMY_URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:{postgres_port}/{db_name}",
            CKAN___BEAKER__SESSION__URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:{postgres_port}/{db_name}",
            CKAN__DATASTORE__READ_URL=f"postgresql://{datastore_ro_user}:{datastore_ro_password}@{postgres_host}:{postgres_port}/{datastore_name}",
            CKAN__DATASTORE__WRITE_URL=f"postgresql://{datastore_name}:{datastore_password}@{postgres_host}:{postgres_port}/{datastore_name}",
            CKAN_SOLR_URL=f"{solr_http_endpoint}/{solr_collection_name}",
            CKANEXT__S3FILESTORE__AWS_STORAGE_PATH=storage_path,
            CKANEXT__S3FILESTORE__AWS_ACCESS_KEY_ID=storage_access_key,
            CKANEXT__S3FILESTORE__AWS_SECRET_ACCESS_KEY=storage_secret_key,
            CKANEXT__S3FILESTORE__AWS_BUCKET_NAME=storage_bucket,
            CKANEXT__S3FILESTORE__HOST_NAME=f'https://{storage_hostname}/',
            CKANEXT__S3FILESTORE__REGION_NAME='us-east-1',
            CKANEXT__S3FILESTORE__SIGNATURE_VERSION='s3v4',
            CKAN__DATAPUSHER__URL=datapusher.get_datapusher_url(envvars.get('CKAN__DATAPUSHER__URL')),
        )
        from ckan_cloud_operator.providers.ckan import manager as ckan_manager
        ckan_manager.update_deis_instance_envvars(self.instance, envvars)
        assert envvars['CKAN_SITE_ID'] and envvars['CKAN_SITE_URL'] and envvars['CKAN_SQLALCHEMY_URL']
        # print(yaml.dump(envvars, default_flow_style=False))
        self._apply_instance_envvars_overrides(envvars)
        envvars = {
            k: ('' if v is None else v)
            for k,v
            in envvars.items()
        }
        kubectl.update_secret('ckan-envvars', envvars, namespace=self.instance.id)
        self.site_url = envvars.get('CKAN_SITE_URL')

    def update(self):
        self.instance.annotations.update_status('envvars', 'created', lambda: self._update(), force_update=True)

    def delete(self):
        print('Deleting instance envvars secret')
        subprocess.check_call(f'kubectl -n {self.instance.id} delete secret/ckan-envvars', shell=True)

    def get(self, full=False):
        exitcode, output = subprocess.getstatusoutput(f'kubectl -n {self.instance.id} get secret/ckan-envvars -o yaml')
        if exitcode == 0:
            secret = kubectl.decode_secret(yaml.load(output))
            res = {'ready': 'CKAN_SITE_URL' in secret}
            if full:
                res['envvars'] = secret
        else:
            res = {'ready': False, 'error': output}
        return res
