import subprocess
import yaml
import os
import json

from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator import logs
from ckan_cloud_operator.providers.routers import manager as routers_provider
from ckan_cloud_operator.providers.ckan import manager as ckan_manager


def get_path_to_old_cluster_kubeconfig():
    return ckan_manager.get_path_to_old_cluster_kubeconfig()


def get_solr_config(old_site_id, path_to_old_cluster_kubeconfig):
    solr_collection_name = old_site_id.replace('-', 'dash')
    output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                     f'kubectl -n solr exec zk-0 zkCli.sh '
                                     f'get /collections/{solr_collection_name} 2>&1', shell=True)
    print(output)
    solr_config = None
    for line in output.decode().splitlines():
        if line.startswith('{"configName":'):
            solr_config = json.loads(line)["configName"]
    return solr_config


def get_instance_env(old_site_id, path_to_old_cluster_kubeconfig):
    output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                     f'kubectl -n {old_site_id} get deployment {old_site_id}-cmd -o yaml',
                                     shell=True)
    deployment = yaml.load(output)
    containers = deployment['spec']['template']['spec']['containers']
    assert len(containers) == 1, f'invalid number of containers {len(containers)}'
    container = containers[0]
    fetch_secret_name = None
    envvar_secrets = {}
    extra_values = {}
    for e in container['env']:
        name = e.pop('name')
        if 'valueFrom' in e:
            value_from = e.pop('valueFrom')
            assert len(e) == 0
            secret_key_ref = value_from.pop('secretKeyRef')
            assert len(value_from) == 0
            secret_key = secret_key_ref.pop('key')
            secret_name = secret_key_ref.pop('name')
            assert len(secret_key_ref) == 0
            assert not fetch_secret_name or fetch_secret_name == secret_name
            fetch_secret_name = secret_name
            envvar_secrets[name] = secret_key
        else:
            value = e.pop('value')
            assert len(e) == 0
            extra_values[name] = value
    output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                     f'kubectl -n {old_site_id} get secret {fetch_secret_name} -o yaml',
                                     shell=True)
    secret = kubectl.decode_secret(yaml.load(output))
    instance_env = {}
    for key, secret_key in envvar_secrets.items():
        instance_env[key] = secret[secret_key]
    return dict(instance_env, **extra_values)


def migrate_from_deis(old_site_id, new_instance_id, router_name, deis_instance_class,
                      skip_gitlab=False, db_migration_name=None, recreate=False,
                      skip_routes=False, skip_solr=False, skip_deployment=False,
                      no_db_proxy=False):
    assert db_migration_name, 'migration without a db migration is not supported yet'
    log_labels = {'instance': new_instance_id}
    if recreate:
        from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
        DeisCkanInstance(new_instance_id).delete(force=True, wait_deleted=not db_migration_name)
    logs.info(f'Migrating from old site id {old_site_id} to new instance id {new_instance_id}', **log_labels)
    instance_kind = ckan_manager.instance_kind()
    values = kubectl.get(f'{instance_kind} {new_instance_id}', required=False)
    if values:
        logs.info('instance already exists', **log_labels)
    else:
        logs.info('creating instance', **log_labels)
        path_to_old_cluster_kubeconfig = get_path_to_old_cluster_kubeconfig()
        solr_config = get_solr_config(old_site_id, path_to_old_cluster_kubeconfig)
        assert solr_config, 'failed to get solr config name'
        instance_env = get_instance_env(old_site_id, path_to_old_cluster_kubeconfig)
        gitlab_repo = f'viderum/cloud-{old_site_id}'
        if not skip_gitlab:
            CkanGitlab().initialize(gitlab_repo)
        gitlab_registry = f'registry.gitlab.com/{gitlab_repo}'
        old_bucket_name = instance_env.get('CKANEXT__S3FILESTORE__AWS_BUCKET_NAME')
        old_storage_path = instance_env.get('CKANEXT__S3FILESTORE__AWS_STORAGE_PATH')
        assert old_bucket_name == 'ckan'
        assert old_storage_path and len(old_storage_path) > 1
        storage_path = f'/ckan/{old_storage_path}'
        deis_instance_class.create('from-gcloud-envvars', instance_env, gitlab_registry, solr_config,
                                   storage_path, new_instance_id, db_migration_name=db_migration_name)
    routers_env_id = routers_provider.get_env_id()
    default_root_domain = routers_provider.get_default_root_domain()
    assert routers_env_id and default_root_domain
    ckan_site_url = f'https://cc-{routers_env_id}-{new_instance_id}.{default_root_domain}'
    logs.info(f'updating instance and setting ckan site url to {ckan_site_url}', **log_labels)
    deis_instance_class(
        new_instance_id,
        override_spec={
            'envvars': {'CKAN_SITE_URL': ckan_site_url}, **(
                {'db': {'no-db-proxy': 'yes'}, 'datastore': {'no-db-proxy': 'yes'}} if no_db_proxy else {}
            )
        },
        persist_overrides=True
    ).update(wait_ready=True, skip_solr=skip_solr, skip_deployment=skip_deployment)
    if routers_manager.get_deis_instance_routes(new_instance_id):
        logs.info('default instance route already exists', **log_labels)
    else:
        logs.info('creating instance route', **log_labels)
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'deis-instance',
            'deis-instance-id': new_instance_id,
            'root-domain': 'default',
            'sub-domain': 'default'
        })
    if not skip_routes:
        routers_manager.update(router_name, wait_ready=True)
    if not skip_solr:
        logs.info('Rebuilding solr search index', **log_labels)
        deis_instance_class(new_instance_id).ckan.paster('search-index rebuild --force')
