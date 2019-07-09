import subprocess
import yaml
import traceback
import time
import json

from ckan_cloud_operator import kubectl
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
from ckan_cloud_operator.monitoring.uptime import DeisCkanInstanceUptime
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.ckan import manager as ckan_manager
from ckan_cloud_operator.providers.ckan.db import migration as ckan_db_migration_manager


class DeisCkanInstance(object):
    """Root object for Deis CKAN instances"""

    @classmethod
    def add_cli_commands(cls, click, command_group, great_success):

        @command_group.command('list')
        @click.option('-f', '--full', is_flag=True)
        @click.option('-q', '--quick', is_flag=True)
        def deis_instance_list(full, quick):
            """List the Deis instances"""
            cls.list(full, quick)

        @command_group.command('get')
        @click.argument('INSTANCE_ID')
        @click.argument('ATTR', required=False)
        def deis_instance_get(instance_id, attr):
            """Get detailed information about an instance, optionally returning only a single get attribute

            Example: ckan-cloud-operator get <INSTANCE_ID> deployment
            """
            print(yaml.dump(cls(instance_id).get(attr), default_flow_style=False))

        @command_group.command('edit')
        @click.argument('INSTANCE_ID')
        @click.argument('EDITOR', default='nano')
        def deis_instance_edit(instance_id, editor):
            """Launch an editor to modify and update an instance"""
            instance_kind = ckan_manager.instance_kind()
            subprocess.call(f'EDITOR={editor} kubectl -n ckan-cloud edit {instance_kind}/{instance_id}', shell=True)
            cls(instance_id).update()
            great_success()

        @command_group.command('update')
        @click.argument('INSTANCE_ID')
        @click.argument('OVERRIDE_SPEC_JSON', required=False)
        @click.option('--persist-overrides', is_flag=True)
        @click.option('--wait-ready', is_flag=True)
        @click.option('--skip-deployment', is_flag=True)
        def deis_instance_update(instance_id, override_spec_json, persist_overrides, wait_ready, skip_deployment):
            """Update an instance to the latest resource spec, optionally applying the given json override to the resource spec

            Examples:

            ckan-cloud-operator update <INSTANCE_ID> '{"envvars":{"CKAN_SITE_URL":"http://localhost:5000"}}' --wait-ready

            ckan-cloud-operator update <INSTANCE_ID> '{"flags":{"skipDbPermissions":false}}' --persist-overrides
            """
            override_spec = json.loads(override_spec_json) if override_spec_json else None
            cls(instance_id, override_spec=override_spec, persist_overrides=persist_overrides).update(
                wait_ready=wait_ready, skip_deployment=skip_deployment
            )
            great_success()

        @command_group.command('delete')
        @click.argument('INSTANCE_ID', nargs=-1)
        @click.option('--force', is_flag=True)
        def deis_instance_delete(instance_id, force):
            """Permanently delete the instances and all related infrastructure"""
            failed_instance_ids = []
            for id in instance_id:
                try:
                    cls(id).delete(force)
                except Exception:
                    traceback.print_exc()
                    failed_instance_ids.append(id)
            if len(failed_instance_ids) > 0:
                logs.critical(f'Instance deletion failed for the following instance ids: {failed_instance_ids}')
                if not force:
                    logs.exit_catastrophic_failure()
            great_success()

        #### deis-instance create

        @command_group.group('create')
        def deis_instance_create():
            """Create and update an instance"""
            pass

        @deis_instance_create.command('from-gitlab')
        @click.argument('GITLAB_REPO_NAME')
        @click.argument('SOLR_CONFIG_NAME')
        @click.argument('NEW_INSTANCE_ID')
        @click.option('--no-db-proxy', is_flag=True)
        @click.option('--from-db-backups')
        @click.option('--storage-path')
        @click.option('--solr-collection')
        @click.option('--rerun', is_flag=True)
        @click.option('--force', is_flag=True)
        @click.option('--recreate-dbs', is_flag=True)
        @click.option('--db-prefix')
        @click.option('--use-private-gitlab-repo', is_flag=True)
        def deis_instance_create_from_gitlab(gitlab_repo_name, solr_config_name, new_instance_id, no_db_proxy,
                                             from_db_backups, storage_path, solr_collection, rerun,
                                             force, recreate_dbs, db_prefix,
                                             use_private_gitlab_repo):
            """Create and update a new instance from a GitLab repo containing Dockerfile and .env

            Example: ckan-cloud-operator deis-instance create from-gitlab viderum/cloud-demo2 ckan_27_default <NEW_INSTANCE_ID>
            """
            cls.create('from-gitlab', gitlab_repo_name, solr_config_name, new_instance_id,
                       no_db_proxy=no_db_proxy, storage_path=storage_path,
                       from_db_backups=from_db_backups, solr_collection=solr_collection,
                       rerun=rerun, force=force, recreate_dbs=recreate_dbs,
                       db_prefix=db_prefix,
                       use_private_gitlab_repo=use_private_gitlab_repo).update()
            great_success()

        #### deis-instance ckan

        @command_group.group('ckan')
        def deis_instance_ckan():
            """Manage a running CKAN instance"""
            pass

        @deis_instance_ckan.command('paster')
        @click.argument('INSTANCE_ID')
        @click.argument('PASTER_ARGS', nargs=-1)
        def deis_instance_ckan_paster(instance_id, paster_args):
            """Run CKAN Paster commands

            Run without PASTER_ARGS to get the available paster commands from the server

            Examples:

              ckan-cloud-operator deis-instance ckan-paster <INSTANCE_ID> sysadmin add admin name=admin email=admin@ckan

              ckan-cloud-operator deis-instance ckan-paster <INSTANCE_ID> search-index rebuild
            """
            cls(instance_id).ckan.run('paster', *paster_args)

        @deis_instance_ckan.command('port-forward')
        @click.argument('INSTANCE_ID')
        @click.argument('PORT', default='5000')
        def deis_instance_port_forward(instance_id, port):
            """Start a port-forward to the CKAN instance pod"""
            cls(instance_id).ckan.run('port-forward', port)

        @deis_instance_ckan.command('exec')
        @click.argument('INSTANCE_ID')
        @click.argument('KUBECTL_EXEC_ARGS', nargs=-1)
        def deis_instance_ckan_exec(instance_id, kubectl_exec_args):
            """Run kubectl exec on the first CKAN instance pod"""
            cls(instance_id).ckan.run('exec', *kubectl_exec_args)

        @deis_instance_ckan.command('logs')
        @click.argument('INSTANCE_ID')
        @click.argument('KUBECTL_LOGS_ARGS', nargs=-1)
        def deis_instance_ckan_logs(instance_id, kubectl_logs_args):
            """Run kubectl logs on the first CKAN instance pod"""
            cls(instance_id).ckan.run('logs', *kubectl_logs_args)

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
            self._values = values = kubectl.get(f'{self.kind} {self.id}')
        return values

    @property
    def kind(self):
        return ckan_manager.instance_kind()

    @property
    def spec(self):
        """Initialize the spec object, fetch values from kubernetes if not provided

        :return: DeisCkanInstanceSpec
        """
        if not getattr(self, '_spec', None):
            self._spec = DeisCkanInstanceSpec(self.values['spec'], self._override_spec)
            if self._persist_overrides and self._spec.num_applied_overrides > 0:
                logs.info('persisting overrides')
                logs.debug(f'saving spec for instance id {self.id}: {self._spec.spec}')
                instance = kubectl.get(f'{self.kind} {self.id}')
                instance['spec'] = self._spec.spec
                logs.debug_yaml_dump(instance)
                kubectl.apply(instance)
        return self._spec

    @property
    def ckan_infra(self):
        """Initialize the infra object, fetching values from Kubernetes secrets

        :return: CkanInfra
        """
        ckan_infra = getattr(self, '_ckan_infra', None)
        if not ckan_infra:
            self._ckan_infra = ckan_infra = CkanInfra(required=False)
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

    def update(self, wait_ready=False, skip_solr=False, skip_deployment=False):
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
        if not skip_solr:
            DeisCkanInstanceSolr(self).update()
        DeisCkanInstanceStorage(self).update()
        DeisCkanInstanceRegistry(self).update()
        envvars = DeisCkanInstanceEnvvars(self)
        envvars.update()
        if not skip_deployment:
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
                        print(yaml.dump(
                            {
                                k: v for k, v in data.items()
                                if (k not in ['ready'] and type(v) == dict and not v.get('ready')) or k == 'namespace'
                            },
                            default_flow_style=False)
                        )
                        time.sleep(2)
        self.ckan.update()
        try:
            DeisCkanInstanceDb(self, 'datastore').set_datastore_readonly_permissions()
        except Exception:
            logs.warning('Setting datastore permissions failed, continuing anyway')
        # Create/Update uptime monitoring after everything else is ready
        DeisCkanInstanceUptime(self).update(envvars.site_url)

    def delete(self, force=False, wait_deleted=False):
        """
        Can run delete multiple time until successful deletion of all components.
        Uses Kubernetes finalizers to ensure deletion is complete before applying the deletion.
        """
        print(f'Deleting {self.kind} {self.id}')
        try:
            assert self.spec
            has_spec = True
        except Exception:
            has_spec = False
        # this updates deletion timestamp but doesn't delete the object until all finalizers are removed
        subprocess.call(f'kubectl -n ckan-cloud delete --wait=false {self.kind} {self.id}', shell=True)
        num_exceptions = 0
        if has_spec:
            for delete_id, delete_code in {
                'deployment': lambda: DeisCkanInstanceDeployment(self).delete(),
                'envvars': lambda: DeisCkanInstanceEnvvars(self).delete(),
                'registry': lambda: DeisCkanInstanceRegistry(self).delete(),
                'solr': lambda: DeisCkanInstanceSolr(self).delete(),
                'storage': lambda: DeisCkanInstanceStorage(self).delete(),
                'namespace': lambda: DeisCkanInstanceNamespace(self).delete(),
                'envvars-secret': lambda: kubectl.check_call(f'delete --ignore-not-found secret/{self.id}-envvars'),
                'routes': lambda: routers_manager.delete_routes(deis_instance_id=self.id),
                'uptime-monitoring': lambda: DeisCkanInstanceUptime(self).delete(self.id)
            }.items():
                try:
                    delete_code()
                except Exception as e:
                    logs.critical(f'deletion failed for instance {self.id}, submodule: {delete_id}')
                    num_exceptions += 1
        else:
            try:
                routers_manager.delete_routes(deis_instance_id=self.id)
            except Exception as e:
                logs.critical(f'deletion failed for instance {self.id}, submodule: routes')
                num_exceptions += 1
            num_exceptions += 1
        if num_exceptions != 0 and not force:
            raise Exception('instance was not deleted, run with --force to force deletion with risk of remaining infra')
        else:
            print(f'Removing finalizers from {self.kind} {self.id}')
            try:
                subprocess.check_call(
                    f'kubectl -n ckan-cloud patch {self.kind} {self.id} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
                    shell=True
                )
            except Exception:
                logs.critical(f'failed to remove finalizers: {self.id}')
                num_exceptions += 1
                if not force:
                    raise
        if wait_deleted and has_spec:
            logs.info('Waiting 30 seconds for instance to be deleted...')
            time.sleep(30)

    def kubectl(self, cmd, check_output=False):
        if check_output:
            return subprocess.check_output(f'kubectl -n {self.id} {cmd}', shell=True)
        else:
            subprocess.check_call(f'kubectl -n {self.id} {cmd}', shell=True)

    def get(self, attr=None, exclude_attr=None):
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
        if exclude_attr:
            gets = {k: v for k, v in gets.items() if k not in exclude_attr}
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
    def list(cls, full=False, quick=False, return_list=False):
        res = []
        data = kubectl.get(ckan_manager.instance_kind(), required=False)
        if not data: data = {'items': []}
        for item in data['items']:
            if quick:
                data = {
                    'id': item['metadata']['name'],
                    'ready': None
                }
                if full:
                    data['item'] = item
            else:
                try:
                    instance = DeisCkanInstance(item['metadata']['name'], values=item)
                    data = instance.get()
                    if not full:
                        data = {'id': instance.id, 'ready': data['ready']}
                except Exception:
                    data = {'id': item['metadata']['name'], 'ready': False, 'error': traceback.format_exc()}
            if return_list:
                res.append(data)
            else:
                print(yaml.dump([data], default_flow_style=False))
        if return_list:
            return res


    @classmethod
    def create(cls, *args, **kwargs):
        create_type = args[0]
        instance_id = args[-1]
        from ckan_cloud_operator.providers.db.manager import get_default_db_prefix
        db_prefix = kwargs['db_prefix'] if kwargs.get('db_prefix') else get_default_db_prefix()
        if create_type == 'from-gitlab':
            gitlab_repo = args[1]
            solr_config = args[2]
            db_name = instance_id
            datastore_name = f'{instance_id}-datastore'
            storage_path = kwargs.get('storage_path') or f'/ckan/{instance_id}'
            from_db_backups = kwargs.get('from_db_backups')
            logs.info(f'Creating Deis CKAN instance {instance_id}', gitlab_repo=gitlab_repo, solr_config=solr_config,
                      db_name=db_name, datastore_name=datastore_name, storage_path=storage_path,
                      from_db_backups=from_db_backups)

            if kwargs.get('use_private_gitlab_repo'):
                deploy_token_server = input('Gitlab registry url [default: registry.gitlab.com]: ') or 'registry.gitlab.com'
                deploy_token_username = input('Gitlab deploy token username: ')
                deploy_token_password = input('Gitlab deploy token password: ')
                kubectl.call('delete secret private-gitlab-registry', namespace=instance_id)
                kubectl.call(f'create secret docker-registry private-gitlab-registry --docker-server={deploy_token_server} --docker-username={deploy_token_username} --docker-password={deploy_token_password}', namespace=instance_id)

            if from_db_backups:
                db_import_url, datastore_import_url = from_db_backups.split(',')
                migration_name = None
                success = False
                for event in ckan_db_migration_manager.migrate_deis_dbs(None, db_name, datastore_name,
                                                                        db_import_url=db_import_url,
                                                                        datastore_import_url=datastore_import_url,
                                                                        rerun=kwargs.get('rerun'),
                                                                        force=kwargs.get('force'),
                                                                        recreate_dbs=kwargs.get('recreate_dbs'),
                                                                        db_prefix=db_prefix):
                    migration_name = ckan_db_migration_manager.get_event_migration_created_name(event) or migration_name
                    success = ckan_db_migration_manager.print_event_exit_on_complete(
                        event,
                        f'DBs import {from_db_backups} -> {db_name}, {datastore_name}',
                        soft_exit=True
                    )
                    if success is not None:
                        break
                assert success, f'Invalid DB migration success value ({success})'
            else:
                migration_name = None
            spec = {
                'ckanPodSpec': {},
                'ckanContainerSpec': {'imageFromGitlab': gitlab_repo},
                'envvars': {'fromGitlab': gitlab_repo},
                'solrCloudCollection': {
                    'name': kwargs.get('solr_collection') or instance_id,
                    'configName': solr_config
                },
                'db': {
                    'name': db_name,
                    **({'fromDbMigration': migration_name} if migration_name else {}),
                    **({'dbPrefix': db_prefix} if db_prefix else {})
                },
                'datastore': {
                    'name': datastore_name,
                    **({'fromDbMigration': migration_name} if migration_name else {}),
                    **({'dbPrefix': db_prefix} if db_prefix else {})
                },
                'storage': {
                    'path': storage_path,
                }
            }
            if kwargs.get('use_private_gitlab_repo'):
                spec['ckanContainerSpec']['imagePullSecrets'] = [{'name': 'private-gitlab-registry'}]
        elif create_type == 'from-gcloud-envvars':
            print(f'Creating Deis CKAN instance {instance_id} from gcloud envvars import')
            instance_env_yaml, image, solr_config, storage_path, instance_id = args[1:]
            db_migration_name = kwargs.get('db_migration_name')
            assert db_migration_name, 'creating from gcloud envvars without a db migration is not supported yet'
            if type(instance_env_yaml) == str:
                logs.info(f'Creating {instance_id}-envvars secret from file: {instance_env_yaml}')
                subprocess.check_call(
                    f'kubectl -n ckan-cloud create secret generic {instance_id}-envvars --from-file=envvars.yaml={instance_env_yaml}',
                    shell=True
                )
            else:
                logs.info(f'Creating {instance_id}-envvars secret from inline string')
                kubectl.update_secret(f'{instance_id}-envvars', {'envvars.yaml': yaml.dump(instance_env_yaml, default_flow_style=False)})
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
                    'fromDbMigration':db_migration_name,
                    **({'dbPrefix': db_prefix} if db_prefix else {})
                },
                'datastore': {
                    'name': f'{instance_id}-datastore',
                    'fromDbMigration': db_migration_name,
                    **({'dbPrefix': db_prefix} if db_prefix else {})
                },
                'storage': {
                    'path': storage_path
                }
            }
        else:
            raise NotImplementedError(f'invalid create type: {create_type}')
        instance_kind = ckan_manager.instance_kind()
        instance = {
            'apiVersion': f'stable.viderum.com/v1',
            'kind': instance_kind,
            'metadata': {
                'name': instance_id,
                'namespace': 'ckan-cloud',
                'finalizers': ['finalizer.stable.viderum.com']
            },
            'spec': spec
        }
        subprocess.run('kubectl apply -f -', input=yaml.dump(instance).encode(), shell=True, check=True)
        return cls(instance_id, values=instance)

    def set_subdomain_route(self, router_type, router_name, route_type, router_annotations):
        assert router_type in ['traefik-subdomain']
        self.annotations.json_annotate(f'router-{route_type}-{router_name}', router_annotations)
