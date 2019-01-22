import subprocess
import yaml
import traceback
import time
import os
import json
import datetime

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import gcloud
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.deis_ckan.ckan import DeisCkanInstanceCKAN
from ckan_cloud_operator.deis_ckan.annotations import DeisCkanInstanceAnnotations
from ckan_cloud_operator.deis_ckan.db import DeisCkanInstanceDb
from ckan_cloud_operator.deis_ckan.deployment import DeisCkanInstanceDeployment
from ckan_cloud_operator.deis_ckan.envvars import DeisCkanInstanceEnvvars
from ckan_cloud_operator.deis_ckan.namespace import DeisCkanInstanceNamespace
from ckan_cloud_operator.deis_ckan.registry import DeisCkanInstanceRegistry
from ckan_cloud_operator.deis_ckan.solr import DeisCkanInstanceSolr
from ckan_cloud_operator.deis_ckan.spec import DeisCkanInstanceSpec
from ckan_cloud_operator.deis_ckan.storage import DeisCkanInstanceStorage


class DeisCkanInstance(object):
    """Root object for Deis CKAN instances"""

    def __init__(self, id, values=None, override_spec=None, persist_overrides=False):
        """
        :param id: Deis CKAN instance id
        :param values: dict containing the relevant DeisCkanInstance Kubernetes object
        :param override_spec: optional dict containing temporary override values for the spec
                              these values are not persistent
        :param persist_overrides: if true the override spec will be persisted

        The DeisCkanInstance object is lazy-loaded, when the object spec is required
        these values will be used to fetch the latest spec
        """
        self.id = id
        self._values = values
        self._override_spec = override_spec
        self._persist_overrides = persist_overrides
        self._override_flags = self._override_spec.pop('flags') if self._override_spec and 'flags' in self._override_spec else None

    @property
    def values(self):
        """Initialize the raw Kubernetes resource object dict"""
        values = getattr(self, '_values', None)
        if not values:
            self._values = values = kubectl.get(f'DeisCkanInstance {self.id}')
        return values

    @property
    def spec(self):
        """Initialize the spec object, fetch values from kubernetes if not provided

        :return: DeisCkanInstanceSpec
        """
        spec = getattr(self, '_spec', None)
        if not spec:
            self._spec = spec = DeisCkanInstanceSpec(self.values['spec'], self._override_spec)
            if self._persist_overrides and spec.num_applied_overrides > 0:
                instance = kubectl.get(f'DeisCkanInstance {self.id}')
                instance['spec'] = spec.spec
                subprocess.run('kubectl apply -f -', input=yaml.dump(instance).encode(), shell=True, check=True)
        return spec

    @property
    def ckan_infra(self):
        """Initialize the infra object, fetching values from Kubernetes secrets

        :return: CkanInfra
        """
        ckan_infra = getattr(self, '_ckan_infra', None)
        if not ckan_infra:
            self._ckan_infra = ckan_infra = CkanInfra()
        return ckan_infra

    @property
    def annotations(self):
        """Initialize the annotations object for storing instance metadata

        :return: DeisCkanInstanceAnnotations
        """
        annotations = getattr(self, '_annotations', None)
        if not annotations:
            self._annotations = annotations = DeisCkanInstanceAnnotations(self, self._override_flags, self._persist_overrides)
        return annotations

    @property
    def ckan(self):
        """Initializes the ckan object for managing running CKAN instances

        :return: DeisCkanInstanceCKAN
        """
        ckan = getattr(self, '_ckan', None)
        if not ckan:
            self._ckan = ckan = DeisCkanInstanceCKAN(self)
        return ckan

    def update(self, wait_ready=False):
        """Ensure the instance is updated to latest spec"""
        old_deployment = kubectl.get(f'deployment {self.id}', required=False, namespace=self.id)
        if old_deployment:
            old_deployment_generation = old_deployment.get('metadata', {}).get('generation')
        else:
            old_deployment_generation = None
        if old_deployment_generation:
            expected_new_deployment_generation = old_deployment_generation + 1
        else:
            expected_new_deployment_generation = 1
        print(f'old deployment generation = {old_deployment_generation}')
        DeisCkanInstanceNamespace(self).update()
        DeisCkanInstanceDb(self, 'db').update()
        DeisCkanInstanceDb(self, 'datastore').update()
        DeisCkanInstanceSolr(self).update()
        DeisCkanInstanceStorage(self).update()
        DeisCkanInstanceRegistry(self).update()
        DeisCkanInstanceEnvvars(self).update()
        DeisCkanInstanceDeployment(self).update()
        while True:
            time.sleep(.2)
            new_deployment = kubectl.get(f'deployment {self.id}', required=False, namespace=self.id)
            if not new_deployment: continue
            new_deployment_generation = new_deployment.get('metadata', {}).get('generation')
            if not new_deployment_generation: continue
            if new_deployment_generation == old_deployment_generation: continue
            if new_deployment_generation != expected_new_deployment_generation:
                raise Exception(f'Invalid generation: {new_deployment_generation} '
                                f'(expected: {expected_new_deployment_generation}')
            print(f'new deployment generation: {new_deployment_generation}')
            break
        if wait_ready:
            print('Waiting for ready status')
            time.sleep(3)
            while True:
                data = self.get()
                if data.get('ready'):
                    print(yaml.dump(data, default_flow_style=False))
                    break
                else:
                    print('.')
                    time.sleep(2)
        self.ckan.update()

    def delete(self, force=False):
        """
        Can run delete multiple time until successful deletion of all components.
        Uses Kubernetes finalizers to ensure deletion is complete before applying the deletion.
        """
        print(f'Deleting DeisCkanInstance {self.id}')
        try:
            assert self.spec
            has_spec = True
        except Exception:
            has_spec = False
        # this updates deletion timestamp but doesn't delete the object until all finalizers are removed
        subprocess.call(f'kubectl -n ckan-cloud delete DeisCkanInstance {self.id}', shell=True)
        if has_spec:
            num_exceptions = 0
            for delete_code in [lambda: DeisCkanInstanceDeployment(self).delete(),
                                lambda: DeisCkanInstanceEnvvars(self).delete(),
                                lambda: DeisCkanInstanceRegistry(self).delete(),
                                lambda: DeisCkanInstanceSolr(self).delete(),
                                lambda: DeisCkanInstanceStorage(self).delete(),
                                lambda: DeisCkanInstanceDb(self, 'datastore').delete(),
                                lambda: DeisCkanInstanceDb(self, 'db').delete(),
                                lambda: DeisCkanInstanceNamespace(self).delete()]:
                try:
                    delete_code()
                except Exception as e:
                    print(f'delete exception: {e}')
                    num_exceptions += 1
        else:
            num_exceptions = 1
        if num_exceptions != 0 and not force:
            print('instance was not deleted, run with --force to force deletion with risk of remaining infra')
        else:
            print(f'Removing finalizers from DeisCkanInstance {self.id}')
            subprocess.check_call(
                f'kubectl -n ckan-cloud patch DeisCkanInstance {self.id} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
                shell=True
            )

    def kubectl(self, cmd):
        subprocess.check_call(f'kubectl -n {self.id} {cmd}', shell=True)

    def get(self, attr=None):
        """Get detailed information about the instance and related components"""
        gets = {
            'annotations': lambda: DeisCkanInstanceAnnotations(self).get(),
            'db': lambda: DeisCkanInstanceDb(self, 'db').get(),
            'datastore': lambda: DeisCkanInstanceDb(self, 'datastore').get(),
            'deployment': lambda: DeisCkanInstanceDeployment(self).get(),
            'envvars': lambda: DeisCkanInstanceEnvvars(self).get(),
            'namespace': lambda: DeisCkanInstanceNamespace(self).get(),
            'registry': lambda: DeisCkanInstanceRegistry(self).get(),
            'solr': lambda: DeisCkanInstanceSolr(self).get(),
            'storage': lambda: DeisCkanInstanceStorage(self).get(),
        }
        if attr:
            return gets[attr]()
        else:
            ret = {'ready': True}
            for k, v in gets.items():
                ret[k] = v()
                if type(ret[k]) == dict and not ret[k].get('ready'):
                    ret['ready'] = False
            ret['id'] = self.id
            return ret

    @classmethod
    def install_crd(cls):
        """Ensures installaion of the Deis CKAN custom resource definitions on the cluster"""
        crd = kubectl.get('crd deisckaninstances.stable.viderum.com', required=False)
        version = 'v1'
        if crd:
            assert crd['spec']['version'] == version
            print('DeisCkanInstance custom resource definitions are up-to-date')
        else:
            print('Creating DeisCkanInstance v1 custom resource definition')
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

    @classmethod
    def list(cls, full=False):
        for item in kubectl.get('DeisCkanInstance')['items']:
            try:
                instance = DeisCkanInstance(item['metadata']['name'], values=item)
                data = instance.get()
                if not full:
                    data = {'id': instance.id, 'ready': data['ready']}
            except Exception:
                data = {'id': item['metadata']['name'], 'ready': False, 'error': traceback.format_exc()}
            print(yaml.dump([data], default_flow_style=False))

    @classmethod
    def create(cls, *args):
        create_type = args[0]
        instance_id = args[-1]
        if create_type == 'from-gitlab':
            gitlab_repo = args[1]
            solr_config = args[2]
            print(f'Creating Deis CKAN instance {instance_id} from Gitlab repo {gitlab_repo}')
            spec = {
                'ckanPodSpec': {},
                'ckanContainerSpec': {'imageFromGitlab': gitlab_repo},
                'envvars': {'fromGitlab': gitlab_repo},
                'solrCloudCollection': {
                    'name': instance_id,
                    'configName': solr_config
                },
                'db': {
                    'name': instance_id,
                },
                'datastore': {
                    'name': f'{instance_id}-datastore',
                },
                'ckan': {
                    'init': [['paster', 'db', 'init'],
                             ['paster', 'db', 'upgrade']]
                }
            }
        elif create_type == 'from-gcloud-envvars':
            print(f'Creating Deis CKAN instance {instance_id} from gcloud envvars import')
            instance_env_yaml, image, solr_config, gcloud_db_url, gcloud_datastore_url, storage_path, instance_id = args[1:]
            subprocess.check_call(
                f'kubectl -n ckan-cloud create secret generic {instance_id}-envvars --from-file=envvars.yaml={instance_env_yaml}',
                shell=True
            )
            spec = {
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
                },
                'storage': {
                    'path': storage_path
                }
            }
        elif create_type == 'from-deis':
            old_instance_id, path_to_all_instances_env_yamls, path_to_old_cluster_kubeconfig, instsance_id = args[1:]
            print(f'Creating Deis CKAN instance {instance_id} from old deis instance {old_instance_id}')
            output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                             f'kubectl -n solr exec zk-0 zkCli.sh '
                                             f'get /collections/{old_instance_id} 2>&1', shell=True)
            solr_config = None
            for line in output.decode().splitlines():
                if line.startswith('{"configName":'):
                    solr_config = json.loads(line)["configName"]
            assert solr_config, 'failed to get solr config name'
            ckan_infra = CkanInfra()
            import_backup = ckan_infra.GCLOUD_SQL_DEIS_IMPORT_BUCKET
            instance_latest_datestring = None
            instance_latest_dt = None
            instance_latest_datastore_datestring = None
            instance_latest_datastore_dt = None
            for line in gcloud.check_output(f"ls 'gs://{import_backup}/postgres/????????/*.sql'",
                                            gsutil=True).decode().splitlines():
                # gs://viderum-deis-backups/postgres/20190122/nav.20190122.dump.sql
                datestring, filename = line.split('/')[4:]
                file_instance = '.'.join(filename.split('.')[:-3])
                is_datastore = file_instance.endswith('-datastore')
                file_instance = file_instance.replace('-datastore', '')
                dt = datetime.datetime.strptime(datestring, '%Y%M%d')
                if file_instance == old_instance_id:
                    if is_datastore:
                        if instance_latest_datastore_dt is None or instance_latest_datastore_dt < dt:
                            instance_latest_datastore_datestring = datestring
                            instance_latest_datastore_dt = dt
                    elif instance_latest_dt is None or instance_latest_dt < dt:
                        instance_latest_datestring = datestring
                        instance_latest_dt = dt
            return cls.create(*['from-gcloud-envvars',
                                os.path.join(path_to_all_instances_env_yamls, f'{old_instance_id}.yaml'),
                                f'registry.gitlab.com/viderum/cloud-{old_instance_id}',
                                solr_config,
                                f'gs://{import_backup}/postgres/{instance_latest_datestring}/{old_instance_id}.{instance_latest_datestring}.dump.sql',
                                f'gs://{import_backup}/postgres/{instance_latest_datastore_datestring}/{old_instance_id}.{instance_latest_datastore_datestring}.dump.sql',
                                f'/ckan/{old_instance_id}',
                                instance_id])
        else:
            raise NotImplementedError(f'invalid create type: {create_type}')
        instance = {
            'apiVersion': 'stable.viderum.com/v1',
            'kind': 'DeisCkanInstance',
            'metadata': {
                'name': instance_id,
                'namespace': 'ckan-cloud',
                'finalizers': ['finalizer.stable.viderum.com']
            },
            'spec': spec
        }
        subprocess.run('kubectl create -f -', input=yaml.dump(instance).encode(), shell=True, check=True)
        return cls(instance_id, values=instance)

    def set_subdomain_route(self, router_type, router_name, route_type, router_annotations):
        assert router_type in ['traefik-subdomain']
        self.annotations.json_annotate(f'router-{route_type}-{router_name}', router_annotations)
