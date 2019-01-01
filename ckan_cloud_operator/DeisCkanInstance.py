import base64
import subprocess
import binascii
import os
import yaml
import datetime
import json
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.datastore_permissions import DATASTORE_PERMISSIONS_SQL_TEMPLATE


def validate_deis_ckan_instance_spec(spec):
    for k, v in spec.items():
        if k == 'ckanPodSpec':
            assert type(v) == dict
        elif k == 'ckanContainerSpec':
            assert type(v) == dict
            assert v['image']
        elif k in ['db', 'datastore']:
            assert type(v) == dict
            assert v['name']
            for k, v in v.items():
                if k == 'name': assert type(v) == str
                elif k == 'importGcloudSqlDumpUrl': assert type(v) == str
                elif k == 'skipPermissions': assert type(v) == bool
                else: raise ValueError(f'Invalid db spec attribute: {k}={v}')
        elif k == 'solrCloudCollection':
            assert type(v) == dict
            assert v['name']
            for k, v in v.items():
                if k == 'name': assert type(v) == str
                elif k == 'configName': assert type(v) == str
                else: raise ValueError(f'Invalid solr cloud collection spec attribute: {k}={v}')
        elif k == 'envvars':
            assert type(v) == dict
            assert v['fromSecret']
            for k, v in v.items():
                if k == 'fromSecret': assert type(v) == str
                elif k == 'overrides': assert type(v) == dict
                else: raise ValueError(f'Invalid envvars spec attribute: {k}={v}')
    assert spec['db']['name'] != spec['datastore']['name']


class DeisCkanInstance(object):

    def __init__(self, id, values=None, override_spec=None):
        self.id = id
        self.values = values
        self.override_spec = override_spec

    def _init_spec(self):
        if not self.values:
            self.values = kubectl.get(f'DeisCkanInstance {self.id}')
        if self.override_spec:
            for k, v in self.override_spec.items():
                if k == 'envvars':
                    print('Applying overrides to instance spec envvars')
                    for kk, vv in v.items():
                        self.values['spec'].setdefault('envvars')[kk] = vv
                elif k in ['db', 'datastore', 'solrCloudCollection']:
                    print(f'Applying overrides to instance spec {k}')
                    for kk, vv in v.items():
                        self.values['spec'].setdefault(k)[kk] = vv
                else:
                    raise NotImplementedError(f'Unsupported instance spec override: {k}: {v}')
        self.spec = spec = self.values['spec']
        validate_deis_ckan_instance_spec(spec)
        self.envvars = spec['envvars']
        if 'fromSecret' in self.envvars:
            self.envvars = kubectl.get(f'secret {self.envvars["fromSecret"]}')
            self.envvars = yaml.load(kubectl.decode_secret(self.envvars, 'envvars.yaml'))
        else:
            raise Exception(f'invalid envvars: {self.envvars}')
        assert self.envvars['CKAN_SITE_ID'] and self.envvars['CKAN_SITE_URL'] and self.envvars['CKAN_SQLALCHEMY_URL']
        self.db = spec['db']
        self.datastore = spec['datastore']
        self.solrCloudCollection = spec['solrCloudCollection']

    def _init_infra_secrets(self):
        self.ckan_infra = kubectl.decode_secret(kubectl.get('secret ckan-infra'))
        for k in ['GCLOUD_SQL_INSTANCE_NAME', 'GCLOUD_SQL_PROJECT', 'POSTGRES_HOST', 'POSTGRES_PASSWORD',
                  'SOLR_HTTP_ENDPOINT', 'SOLR_NUM_SHARDS', 'SOLR_REPLICATION_FACTOR',
                  'DOCKER_REGISTRY_SERVER', 'DOCKER_REGISTRY_USERNAME', 'DOCKER_REGISTRY_PASSWORD', 'DOCKER_REGISTRY_EMAIL']:
            assert self.ckan_infra[k]

    def _psql(self, cmd, *args):
        postgres_host = self.ckan_infra['POSTGRES_HOST']
        postgres_password = self.ckan_infra['POSTGRES_PASSWORD']
        postgres_user = self.ckan_infra['POSTGRES_USER']
        subprocess.check_call(['psql', '-v', 'ON_ERROR_STOP=on', '-h', postgres_host, '-U', postgres_user, *args, '-c', cmd],
                              env={'PGPASSWORD': postgres_password})

    def _set_db_permissions(self, db_name, db_values):
        if not db_values.get('skipPermissions'):
            print('setting db permissions')
            for line in [
                f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" to "{db_name}";'
                f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public to "{db_name}";'
                f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to "{db_name}";'
                f"ALTER DATABASE \"{db_name}\" OWNER TO \"{db_name}\";",
            ]:
                self._psql(line, '-d', db_name)

    def _set_datastore_permissions(self, db_name, db_values):
        if not db_values.get('skipPermissions'):
            print('setting datastore permissions')
            ro_user = f'{db_name}-ro'
            site_user = self.db['name']
            postgres_user = self.ckan_infra['POSTGRES_USER']
            for line in [
                f"REVOKE CREATE ON SCHEMA public FROM PUBLIC;",
                f"REVOKE USAGE ON SCHEMA public FROM PUBLIC;",
                f"GRANT CREATE ON SCHEMA public TO \"{site_user}\";",
                f"GRANT USAGE ON SCHEMA public TO \"{site_user}\";",
                f"GRANT CREATE ON SCHEMA public TO \"{db_name}\";",
                f"GRANT USAGE ON SCHEMA public TO \"{db_name}\";",
                f"GRANT \"{site_user}\" TO \"{postgres_user}\";",
                f"ALTER DATABASE \"{site_user}\" OWNER TO {postgres_user};",
                f"ALTER DATABASE \"{db_name}\" OWNER TO {postgres_user};",
                f"REVOKE CONNECT ON DATABASE \"{site_user}\" FROM \"{ro_user}\";",
                f"GRANT CONNECT ON DATABASE \"{db_name}\" TO \"{ro_user}\";",
                f"GRANT USAGE ON SCHEMA public TO \"{ro_user}\";",
                f"ALTER DATABASE \"{site_user}\" OWNER TO \"{site_user}\";",
                f"GRANT \"{db_name}\" TO \"{postgres_user}\";",
                f"ALTER DATABASE \"{db_name}\" OWNER TO \"{db_name}\";",
                f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{ro_user}\";",
                f"ALTER DEFAULT PRIVILEGES FOR USER \"{db_name}\" IN SCHEMA public GRANT SELECT ON TABLES TO \"{ro_user}\";"
            ]:
                self._psql(line, '-d', db_name)
            datastore_permissions = DATASTORE_PERMISSIONS_SQL_TEMPLATE.replace('{{SITE_USER}}', site_user).replace('{{DS_RO_USER}}', ro_user)
            self._psql(datastore_permissions, "-d", db_name)

    def _create_datastore_ro_user(self, db_name, db_values):
        ro_user = db_values['ro_user'] = f'{db_name}-ro'
        ro_password = db_values['ro_password'] = binascii.hexlify(os.urandom(12)).decode()
        self._psql(
            f"CREATE ROLE \"{ro_user}\" WITH LOGIN PASSWORD '{ro_password}' NOSUPERUSER NOCREATEDB NOCREATEROLE;"
        )

    def _set_gcloud_storage_sql_permissions(self, importUrl):
        print('setting permissions to cloud storage for import to sql')
        gcloud_sql_instance_name = self.ckan_infra['GCLOUD_SQL_INSTANCE_NAME']
        gcloud_sql_project = self.ckan_infra['GCLOUD_SQL_PROJECT']
        gcloud_sql_instance = yaml.load(subprocess.check_output(
            f'gcloud --project={gcloud_sql_project} sql instances describe {gcloud_sql_instance_name}', shell=True))
        gcloud_sql_service_account_email = gcloud_sql_instance['serviceAccountEmailAddress']
        subprocess.check_call(f'gsutil acl ch -u {gcloud_sql_service_account_email}:R {importUrl}', shell=True)

    def _create_base_db(self, db_name, db_values):
        print('Creating base db')
        db_values['password'] = db_password = binascii.hexlify(os.urandom(12)).decode()
        self._psql(
            f'CREATE ROLE "{db_name}" WITH LOGIN PASSWORD \'{db_password}\' NOSUPERUSER NOCREATEDB NOCREATEROLE;')
        self._psql(f'CREATE DATABASE "{db_name}";')

    def _initialize_db_postgis(self, db_name):
        print('initializing postgis extensions')
        self._psql('CREATE EXTENSION IF NOT EXISTS postgis;', '-d', db_name)
        self._psql('CREATE EXTENSION IF NOT EXISTS postgis_topology;', '-d', db_name)
        self._psql('CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;', '-d', db_name)
        self._psql('CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;', '-d', db_name)

    def _import_gcloud_sql_db(self, db_name, db_type, db_values):
        self._create_base_db(db_name, db_values)
        if db_type == 'db':
            self._initialize_db_postgis(db_name)
        importUrl = db_values["importGcloudSqlDumpUrl"]
        self._set_gcloud_storage_sql_permissions(importUrl)
        print(f'Importing Gcloud SQL from: {importUrl}')
        gcloud_sql_instance_name = self.ckan_infra['GCLOUD_SQL_INSTANCE_NAME']
        gcloud_sql_project = self.ckan_infra['GCLOUD_SQL_PROJECT']
        postgres_user = self.ckan_infra['POSTGRES_USER']
        subprocess.check_call(f'gcloud --project={gcloud_sql_project} --quiet sql import sql {gcloud_sql_instance_name}'
                              f' {importUrl} --database={db_name} --user={postgres_user}', shell=True)
        if db_type == 'datastore':
            self._create_datastore_ro_user(db_name, db_values)

    def _update_db(self, db_type, db_values):
        db_name = db_values['name']
        if self.is_existing_namespace:
            # TODO: verify existing instance DB?
            pass
        elif 'importGcloudSqlDumpUrl' in db_values:
            self._import_gcloud_sql_db(db_name, db_type, db_values)
        else:
            raise NotImplementedError(f'Unsupported db values: {db_values}')
        self._set_db_permissions(db_name, db_values)
        if db_type == 'datastore':
            self._set_datastore_permissions(db_name, db_values)

    def _update_solr(self, solrCloudCollection):
        collection_name = solrCloudCollection['name']
        if self.is_existing_namespace:
            # TODO: verify existing instance solr collection?
            pass
        elif 'configName' in solrCloudCollection:
            config_name = solrCloudCollection['configName']
            print(f'creating solrcloud collection {collection_name} using config {config_name}')
            http_endpoint = self.ckan_infra['SOLR_HTTP_ENDPOINT']
            replication_factor = self.ckan_infra['SOLR_REPLICATION_FACTOR']
            num_shards = self.ckan_infra['SOLR_NUM_SHARDS']
            subprocess.check_call(f'curl -f "{http_endpoint}/admin/collections?action=CREATE&name={collection_name}&collection.configName={config_name}&replicationFactor={replication_factor}&numShards={num_shards}"', shell=True)
        else:
            raise NotImplementedError(f'Unsupported solr cloud collection values: {solrCloudCollection}')

    def _apply_instance_envvars_overrides(self, instance_envvars_secret):
        if 'overrides' in self.values['spec']['envvars']:
            print('Applying instance envvars overrides')
            for k, v in self.values['spec']['envvars']['overrides'].items():
                instance_envvars_secret['data'][k] = base64.b64encode(v.encode()).decode()

    def _update_instance_envvars_secret(self):
        if not kubectl.get(f'secret ckan-envvars', required=False, namespace=self.id):
            self._create_instance_envvars_secret()
        else:
            instance_envvars_secret = {'apiVersion': 'v1',
                                       'kind': 'Secret',
                                       'metadata': {
                                           'name': 'ckan-envvars',
                                           'namespace': self.id
                                       },
                                       'type': 'Opaque',
                                       'data': {}}
            for k, v in kubectl.get('secret ckan-envvars', namespace=self.id)['data'].items():
                instance_envvars_secret['data'][k] = v
            self._apply_instance_envvars_overrides(instance_envvars_secret)
            print('Deleting existing instance envvars secret')
            subprocess.check_call(f'kubectl -n {self.id} delete secret ckan-envvars', shell=True)
            print('Creating instance envvars secret')
            subprocess.run('kubectl create -f -', input=yaml.dump(instance_envvars_secret).encode(),
                           shell=True, check=True)

    def _get_new_instance_envvars_secret(self):
        db_name = self.db['name']
        db_password = self.db['password']
        postgres_host = self.ckan_infra['POSTGRES_HOST']
        datastore_name = self.datastore['name']
        datastore_password = self.datastore['password']
        datastore_ro_user = self.datastore['ro_user']
        datastore_ro_password = self.datastore['ro_password']
        solr_http_endpoint = self.ckan_infra['SOLR_HTTP_ENDPOINT']
        solr_collection_name = self.solrCloudCollection['name']
        self.envvars.update(
            CKAN_SQLALCHEMY_URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:5432/{db_name}",
            CKAN___BEAKER__SESSION__URL=f"postgresql://{db_name}:{db_password}@{postgres_host}:5432/{db_name}",
            CKAN__DATASTORE__READ_URL=f"postgresql://{datastore_ro_user}:{datastore_ro_password}@{postgres_host}:5432/{datastore_name}",
            CKAN__DATASTORE__WRITE_URL=f"postgresql://{datastore_name}:{datastore_password}@{postgres_host}:5432/{datastore_name}",
            CKAN_SOLR_URL=f"{solr_http_endpoint}/{solr_collection_name}"
        )
        instance_envvars_secret = {'apiVersion': 'v1',
                                   'kind': 'Secret',
                                   'metadata': {
                                       'name': 'ckan-envvars',
                                       'namespace': self.id
                                   },
                                   'type': 'Opaque',
                                   'data': {k: base64.b64encode(v.encode()).decode()
                                            for k, v in self.envvars.items()}}
        self._apply_instance_envvars_overrides(instance_envvars_secret)
        return instance_envvars_secret

    def _create_instance_envvars_secret(self):
        print('Creating instance envvars secret')
        subprocess.run('kubectl create -f -', input=yaml.dump(self._get_new_instance_envvars_secret()).encode(),
                       shell=True, check=True)

    def _update_instance_regsitry_secret(self):
        if not kubectl.get(f'secret {self.id}-registry', required=False, namespace=self.id):
            self._create_instance_registry_secret()
        else:
            print('WARNING! instance registry secret was not updated')

    def _create_instance_registry_secret(self):
        print('Creating instance registry secret')
        docker_server = self.ckan_infra['DOCKER_REGISTRY_SERVER']
        docker_username = self.ckan_infra['DOCKER_REGISTRY_USERNAME']
        docker_password = self.ckan_infra['DOCKER_REGISTRY_PASSWORD']
        docker_email = self.ckan_infra['DOCKER_REGISTRY_EMAIL']
        subprocess.check_call(f'kubectl -n {self.id} create secret docker-registry {self.id}-registry '
                              f'--docker-password={docker_password} '
                              f'--docker-server={docker_server} '
                              f'--docker-username={docker_username} '
                              f'--docker-email={docker_email}', shell=True)

    def _deploy_instance(self):
        print(f'Deploying instance {self.id}')
        ckanContainerSpec = dict(self.spec['ckanContainerSpec'],
                                 name='ckan',
                                 envFrom=[{'secretRef': {'name': 'ckan-envvars'}}])
        ckanPodSpec = dict(self.spec['ckanPodSpec'],
                           serviceAccountName=f'ckan-{self.id}-operator',
                           containers=[ckanContainerSpec],
                           imagePullSecrets=[{'name': f'{self.id}-registry'}])
        deployment = {'apiVersion': 'apps/v1beta1',
                      'kind': 'Deployment',
                      'metadata': {
                          'name': self.id,
                          'namespace': self.id
                      },
                      'spec': {
                          'replicas': 1,
                          'revisionHistoryLimit': 5,
                          'template': {
                              'metadata': {
                                  'labels': {
                                      'app': 'ckan'
                                  },
                                  'annotations': {
                                      'ckan-cloud-operator-timestamp': str(datetime.datetime.now())
                                  }
                              },
                              'spec': ckanPodSpec
                          }
                      }}
        subprocess.run('kubectl apply -f -', input=yaml.dump(deployment).encode(), shell=True, check=True)

    def _initialize_instance_namespace(self):
        ns = self.id
        print(f'initializing instance namespace: {ns}')
        subprocess.check_call(f'kubectl create ns {ns}', shell=True)
        kubectl_namespace = f'kubectl --namespace {ns}'
        subprocess.check_call(f'{kubectl_namespace} create serviceaccount ckan-{ns}-operator', shell=True)
        subprocess.check_call(f'{kubectl_namespace} create role ckan-{ns}-operator-role '
                              f' --verb list,get,create --resource secrets,pods,pods/exec,pods/portforward', shell=True)
        subprocess.check_call(f'{kubectl_namespace} create rolebinding ckan-{ns}-operator-rolebinding'
                              f' --role ckan-{ns}-operator-role'
                              f' --serviceaccount {ns}:ckan-{ns}-operator', shell=True)

    def _create_instance(self):
        self._create_instance_envvars_secret()
        self._create_instance_registry_secret()
        self._deploy_instance()

    def _update_instance(self):
        self._update_instance_envvars_secret()
        self._update_instance_regsitry_secret()
        self._deploy_instance()

    def _delete_instance(self):
        print(f'Deleting instance {self.id}')
        subprocess.check_call(f'kubectl -n {self.id} delete deployment/{self.id} --force --now')
        subprocess.check_call(f'kubectl -n {self.id} delete secret/ckan-envvars')

    def _delete_solr(self, solrCloudCollection):
        raise NotImplementedError()

    def _delete_db(self, db_type, db_values):
        raise NotImplementedError()

    def _delete_instance_namespace(self):
        raise NotImplementedError()

    def update(self):
        self._init_infra_secrets()
        self._init_spec()
        try:
            namespace = kubectl.get(f'ns {self.id}')
        except subprocess.CalledProcessError:
            namespace = None
        self.is_existing_namespace = namespace is not None
        if not self.is_existing_namespace:
            self._initialize_instance_namespace()
        self._update_db('db', self.db)
        self._update_db('datastore', self.datastore)
        self._update_solr(self.solrCloudCollection)
        if self.is_existing_namespace:
            self._update_instance()
        else:
            self._create_instance()

    def delete(self):
        self._init_infra_secrets()
        self._init_spec()
        self._delete_instance()
        self._delete_solr(self.solrCloudCollection)
        self._delete_db('datastore', self.datastore)
        self._delete_db('db', self.db)
        self._delete_instance_namespace()

    def run_ckan_paster(self, paster_command=None, *paster_args):
        pods = kubectl.get('pod -l app=ckan', namespace=self.id)['items']
        pod_name = pods[0]['metadata']['name']
        cmd = ['kubectl', '-n', self.id, 'exec', '-it', pod_name, '--', 'paster', '--plugin=ckan']
        if paster_command:
            cmd += [paster_command, '-c', '/srv/app/production.ini', *paster_args]
        subprocess.check_call(cmd)

    def exec(self, *args):
        pods = kubectl.get('pod -l app=ckan', namespace=self.id)['items']
        pod_name = pods[0]['metadata']['name']
        subprocess.check_call(['kubectl', '-n', self.id, 'exec', pod_name, '--', *args])

    def port_forward(self, *args):
        if len(args) == 0:
            args = ['5000']
        subprocess.check_call(['kubectl', '-n', self.id, 'port-forward', f'deployment/{self.id}', *args])

    def get(self):
        self._init_infra_secrets()
        self._init_spec()
        data = {'id': self.id,
                'ckanPodSpec': self.spec['ckanPodSpec'],
                'ckanContainerSpec': self.spec['ckanContainerSpec'],
                'solrCloudCollection': {'name': self.solrCloudCollection['name']}}
        gcloud_sql_instance_name = self.ckan_infra['GCLOUD_SQL_INSTANCE_NAME']
        gcloud_sql_project = self.ckan_infra['GCLOUD_SQL_PROJECT']
        db_name = self.db['name']
        data['db'] = yaml.load(subprocess.check_output(
            f'gcloud -q --project={gcloud_sql_project} '
            f'sql databases describe {db_name} '
            f'--instance {gcloud_sql_instance_name}',
            shell=True
        ).decode())
        datastore_name = self.datastore['name']
        data['datastore'] = yaml.load(subprocess.check_output(
            f'gcloud -q --project={gcloud_sql_project} '
            f'sql databases describe {datastore_name} '
            f'--instance {gcloud_sql_instance_name}',
            shell=True
        ).decode())
        solr_http_endpoint = self.ckan_infra['SOLR_HTTP_ENDPOINT']
        collection_name = self.solrCloudCollection['name']
        res = json.loads(subprocess.check_output(f'curl -s -f "{solr_http_endpoint}/{collection_name}/schema"', shell=True))
        data['solrCloudCollection'].update(schemaVersion=res['schema']['version'], schemaName=res['schema']['name'])
        print(yaml.dump(data, default_flow_style=False))

    @classmethod
    def install_crd(cls):
        try:
            crd = kubectl.get('crd deisckaninstances.stable.viderum.com')
        except subprocess.CalledProcessError:
            crd = {'apiVersion': 'apiextensions.k8s.io/v1beta1',
                   'kind': 'CustomResourceDefinition',
                   'metadata': {
                       'name': 'deisckaninstances.stable.viderum.com'
                   },
                   'spec': {
                       'version': 'v1',
                       'group': 'stable.viderum.com',
                       'scope': 'Namespaced',
                       'names': {
                           'plural': 'deisckaninstances',
                           'singular': 'deisckaninstance',
                           'kind': 'DeisCkanInstance'
                       }
                   }}
            subprocess.run('kubectl create -f -', input=yaml.dump(crd).encode(), shell=True, check=True)
        assert crd['spec']['version'] == 'v1'

    @classmethod
    def list(cls, *args):
        instances = []
        for instance in kubectl.get('DeisCkanInstance')['items']:
            instances.append({'name': instance['metadata']['name']})
        print(yaml.dump(instances, default_flow_style=False))

    @classmethod
    def envvars_gcloud_import(cls, instance_env_yaml, image, solr_config, gcloud_db_url, gcloud_datastore_url, instance_id):
        print(f'Creating envvars secret {instance_id}-envvars in namespace ckan-cloud using file {instance_env_yaml}')
        subprocess.check_call(f'kubectl -n ckan-cloud create secret generic {instance_id}-envvars --from-file=envvars.yaml={instance_env_yaml}', shell=True)
        print(f'Creating DeisCkanInstance {instance_id}')
        instance = {'apiVersion': 'stable.viderum.com/v1',
                    'kind': 'DeisCkanInstance',
                    'metadata': {
                        'name': instance_id,
                        'namespace': 'ckan-cloud',
                        'finalizers': ['finalizer.stable.viderum.com']
                    },
                    'spec': {
                        'ckanPodSpec': {},
                        'ckanContainerSpec': {'image': image},
                        'envvars': {'fromSecret': f'{instance_id}-envvars'},
                        'solrCloudCollection': {
                            'name': instance_id,
                            'configName': solr_config
                        },
                        'db': {
                            'name': instance_id,
                            'importGcloudSqlDumpUrl': gcloud_db_url
                        },
                        'datastore': {
                            'name': f'{instance_id}-datastore',
                            'importGcloudSqlDumpUrl': gcloud_datastore_url
                        }
                    }}
        subprocess.run('kubectl create -f -', input=yaml.dump(instance).encode(), shell=True, check=True)
        return cls(instance_id, values=instance)
