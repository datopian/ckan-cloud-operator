import subprocess
import yaml
import os
import json
import datetime

from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import gcloud
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator import logs


def get_path_to_old_cluster_kubeconfig(ckan_infra):
    path_to_kubeconfig = '/etc/ckan-cloud/viderum-omc/.kube-config'
    if not os.path.exists(path_to_kubeconfig):
        deis_kubeconfig = yaml.load(ckan_infra.DEIS_KUBECONFIG)
        for filename, content in deis_kubeconfig['__files'].items():
            if not os.path.exists(filename):
                print(f'creating file required for deis kubeconfig: {filename}')
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w') as f:
                    f.write(content)
                print('file created successfully')
        print(f'creating deis kubeconfig: {path_to_kubeconfig}')
        os.makedirs(os.path.dirname(path_to_kubeconfig), exist_ok=True)
        with open(path_to_kubeconfig, 'w') as f:
            f.write(yaml.dump(deis_kubeconfig))
        print('created deis kubeconfig')
    return path_to_kubeconfig


def get_solr_config(old_site_id, path_to_old_cluster_kubeconfig):
    solr_collection_name = old_site_id.replace('-', 'dash')
    output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                     f'kubectl -n solr exec zk-0 zkCli.sh '
                                     f'get /collections/{solr_collection_name} 2>&1', shell=True)
    solr_config = None
    for line in output.decode().splitlines():
        if line.startswith('{"configName":'):
            solr_config = json.loads(line)["configName"]
    return solr_config


def get_db_import_urls(old_site_id, ckan_infra):
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
        if file_instance == old_site_id:
            if is_datastore:
                if instance_latest_datastore_dt is None or instance_latest_datastore_dt < dt:
                    instance_latest_datastore_datestring = datestring
                    instance_latest_datastore_dt = dt
            elif instance_latest_dt is None or instance_latest_dt < dt:
                instance_latest_datestring = datestring
                instance_latest_dt = dt
    return (
        f'gs://{import_backup}/postgres/{instance_latest_datestring}/{old_site_id}.{instance_latest_datestring}.dump.sql',
        f'gs://{import_backup}/postgres/{instance_latest_datastore_datestring}/{old_site_id}-datastore.{instance_latest_datastore_datestring}.dump.sql'
    )


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
    for e in container['env']:
        name = e.pop('name')
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
    output = subprocess.check_output(f'KUBECONFIG={path_to_old_cluster_kubeconfig} '
                                     f'kubectl -n {old_site_id} get secret {fetch_secret_name} -o yaml',
                                     shell=True)
    secret = kubectl.decode_secret(yaml.load(output))
    instance_env = {}
    for key, secret_key in envvar_secrets.items():
        instance_env[key] = secret[secret_key]
    return instance_env


def migrate_from_deis(old_site_id, new_instance_id, router_name, deis_instance_class,
                      only_dbs=False):
    log_labels = {'instance': new_instance_id}
    logs.info(f'Migrating from old site id {old_site_id} to new instance id {new_instance_id}', **log_labels)
    values = kubectl.get(f'DeisCkanInstance {new_instance_id}', required=False)
    ckan_infra = CkanInfra()
    if values:
        logs.info('instance already exists', **log_labels)
    else:
        logs.info('creating instance', **log_labels)
        path_to_old_cluster_kubeconfig = get_path_to_old_cluster_kubeconfig(ckan_infra)
        solr_config = get_solr_config(old_site_id, path_to_old_cluster_kubeconfig)
        assert solr_config, 'failed to get solr config name'
        db_import_url, datastore_import_url = get_db_import_urls(old_site_id, ckan_infra)
        instance_env = get_instance_env(old_site_id, path_to_old_cluster_kubeconfig)
        gitlab_repo = f'viderum/cloud-{old_site_id}'
        CkanGitlab(CkanInfra()).initialize(gitlab_repo)
        gitlab_registry = f'registry.gitlab.com/{gitlab_repo}'
        storage_path = f'/ckan/{old_site_id}'
        deis_instance_class.create('from-gcloud-envvars', instance_env, gitlab_registry, solr_config,
                                   db_import_url, datastore_import_url, storage_path, new_instance_id)
    routers_env_id = ckan_infra.ROUTERS_ENV_ID
    assert routers_env_id
    ckan_site_url = f'https://cc-{routers_env_id}-{new_instance_id}.{ckan_infra.ROUTERS_DEFAULT_ROOT_DOMAIN}'
    logs.info(f'updating instance and setting ckan site url to {ckan_site_url}', **log_labels)
    deis_instance_class(
        new_instance_id, values,
        override_spec={'envvars': {'CKAN_SITE_URL': ckan_site_url}},
        persist_overrides=True
    ).update(wait_ready=True, only_dbs=only_dbs)
    if not only_dbs:
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
        routers_manager.update(router_name, wait_ready=True)
        logs.info('Rebuilding solr search index', **log_labels)
        deis_instance_class(new_instance_id).ckan.paster('search-index rebuild --force')
