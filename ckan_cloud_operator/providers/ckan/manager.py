import binascii
import os
import yaml
import traceback
import time
import json
import datetime
from pathlib import Path

from ckan_cloud_operator import logs
from ckan_cloud_operator import kubectl

from ckan_cloud_operator.crds import manager as crds_manager
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.providers.ckan.deployment import manager as deployment_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager
from ckan_cloud_operator.labels import manager as labels_manager

from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.deis_ckan.migrate import migrate_from_deis

from .db import migration as ckan_db_migration_manager

from .constants import INSTANCE_CRD_SINGULAR, INSTANCE_CRD_PLURAL_SUFFIX, INSTANCE_CRD_KIND_SUFFIX
from .constants import INSTANCE_NAME_CRD_SINGULAR, INSTANCE_NAME_CRD_KIND_SUFFIX, INSTANCE_NAME_CRD_PLURAL_SUFFIX


def initialize(interactive=False):
    ckan_db_migration_manager.initialize(interactive=interactive)
    registry_secrets = config_manager.interactive_set(
        {'disable-centralized-datapushers': 'no'},
        configmap_name='global-ckan-config',
        interactive=interactive
    )
    registry_secrets = config_manager.interactive_set(
        {'private-registry': 'n'},
        secret_name='ckan-docker-registry',
        interactive=interactive
    )
    if registry_secrets.get('private-registry') == 'y':
        registry_secrets = config_manager.interactive_set(
            {
                'docker-server': None,
                'docker-username': None,
                'docker-password': None,
                'docker-email': None,
                'docker-image-pull-secret-name': 'container-registry',
            },
            secret_name='ckan-docker-registry',
            interactive=interactive
        )
    if config_manager.get('enable-deis-ckan', configmap_name='global-ckan-config') == 'y':
        ckan_infra = CkanInfra(required=False)
        config_manager.interactive_set(
            {
                'deis-kubeconfig': ckan_infra.DEIS_KUBECONFIG,
            },
            from_file=True,
            secret_name='ckan-migration-secrets',
            interactive=interactive
        )
        config_manager.interactive_set(
            {
                'gitlab-token': ckan_infra.GITLAB_TOKEN_PASSWORD,
            },
            secret_name='ckan-migration-secrets',
            interactive=interactive
        )
        config_manager.interactive_set(
            {
                'docker-server': ckan_infra.DOCKER_REGISTRY_SERVER,
                'docker-username': ckan_infra.DOCKER_REGISTRY_USERNAME,
                'docker-password': ckan_infra.DOCKER_REGISTRY_PASSWORD,
                'docker-email': ckan_infra.DOCKER_REGISTRY_EMAIL,
            },
            secret_name='ckan-docker-registry',
            interactive=interactive
        )
    crds_manager.install_crd(INSTANCE_CRD_SINGULAR, INSTANCE_CRD_PLURAL_SUFFIX, INSTANCE_CRD_KIND_SUFFIX)
    crds_manager.install_crd(INSTANCE_NAME_CRD_SINGULAR, INSTANCE_NAME_CRD_PLURAL_SUFFIX, INSTANCE_NAME_CRD_KIND_SUFFIX)

    from ckan_cloud_operator.providers.solr.manager import zk_list_configs, zk_put_configs
    logs.info('Checking CKAN Solr config in ZooKeeper')
    if 'ckan_default' in zk_list_configs():
        logs.info('Found ckan_default Solr config')
    else:
        logs.info('No default Solr config found. Putting CKAN 2.8 config for Solr to ZooKeeper as ckan_default...')
        file_path = os.path.dirname(os.path.abspath(__file__))
        root_path = Path(file_path).parent.parent
        configs_dir = os.path.join(root_path, 'data', 'solr')
        zk_put_configs(configs_dir)


    if config_manager.get('disable-centralized-datapushers', configmap_name='global-ckan-config', required=False) != 'yes':
        from ckan_cloud_operator.datapushers import initialize as datapusher_initialize
        datapusher_initialize()

    from ckan_cloud_operator.routers import manager as routers_manager
    from ckan_cloud_operator.providers.routers import manager as router_provider_manager
    router_name = get_default_instances_router_name()
    wildcard_ssl_domain = routers_manager.get_default_root_domain()
    dns_provider = router_provider_manager.get_dns_provider()
    logs.info(f'wildcard_ssl_domain={wildcard_ssl_domain} dns_provider={dns_provider}')
    allow_wildcard_ssl = routers_manager.get_env_id() == 'p'
    router = routers_manager.get(router_name, required=False)
    if router:
        assert (
            (allow_wildcard_ssl and router.get('spec', {}).get('wildcard-ssl-domain') == wildcard_ssl_domain)
            or
            (not allow_wildcard_ssl and not router.get('spec', {}))
        ), f'invalid router wildcard ssl config: {router}'
    else:
        # We don't want to create traefik routes if no dns_provider, unless it's minikube
        if dns_provider.lower() == 'none' and cluster_manager.get_provider_id() != 'minikube':
            pass
        else:
            routers_manager.create(
                router_name,
                routers_manager.get_traefik_router_spec(
                    dns_provider=dns_provider,
                    wildcard_ssl_domain=wildcard_ssl_domain
                )
            )

    from .storage.manager import initialize as ckan_storage_initialize
    ckan_storage_initialize(interactive=interactive)

    from .deployment.manager import initialize as ckan_deployment_initialize
    ckan_deployment_initialize(interactive=interactive)


def get_docker_credentials():
    return [
        config_manager.get(key, secret_name='ckan-docker-registry', required=True)
        for key in ['docker-server', 'docker-username', 'docker-password', 'docker-email']
    ]


def get_default_instances_router_name():
    return 'instances-default'


def migrate_deis_instance(old_site_id, new_instance_id=None, router_name=None, skip_gitlab=False,
                          force=False, rerun=False, recreate_dbs=False, recreate=False, recreate_instance=False,
                          skip_routes=False, skip_solr=False, skip_deployment=False, no_db_proxy=False):
    """Run a full end-to-end migration of an instasnce"""
    from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
    if not router_name:
        router_name = get_default_instances_router_name()
    if not new_instance_id:
        new_instance_id = old_site_id
    if recreate or recreate_instance:
        DeisCkanInstance(new_instance_id).delete(force=True, wait_deleted=True)
    success = False
    db_name = f'{new_instance_id}'
    datastore_name = f'{new_instance_id}-datastore'
    migration_name = None
    for event in ckan_db_migration_manager.migrate_deis_dbs(
            old_site_id, db_name, datastore_name,
            force=force or recreate,
            rerun=rerun or recreate,
            recreate_dbs=recreate_dbs or recreate
    ):
        migration_name = ckan_db_migration_manager.get_event_migration_created_name(event) or migration_name
        success = ckan_db_migration_manager.print_event_exit_on_complete(
            event,
            f'DBs Migration from old site ID: {old_site_id}',
            soft_exit=True
        )
        if success is not None:
            break
    assert success, f'Invalid DB migration success value ({success})'
    logs.info('DB migration completed successfully, continuing with instance migration')
    migrate_from_deis(
        old_site_id, new_instance_id, router_name, DeisCkanInstance,
        skip_gitlab=skip_gitlab, db_migration_name = migration_name,
        recreate=recreate or recreate_instance,
        skip_routes=skip_routes,
        skip_solr=skip_solr,
        skip_deployment=skip_deployment,
        no_db_proxy=no_db_proxy
    )
    post_create_checks(new_instance_id)


def deis_kubeconfig():
    return config_manager.get('deis-kubeconfig', secret_name='ckan-migration-secrets', required=True)


def gitlab_token(token_name=None):
    if token_name:
        return config_manager.get(token_name, secret_name='ckan-gitlab-tokens', required=True)
    else:
        return config_manager.get('gitlab-token', secret_name='ckan-migration-secrets', required=True)


def get_jenkins_token(token_name=None):
    return config_manager.get(secret_name='ckan-jenkins-tokens', key=token_name, required=True).split(',')


def gitlab_search_replace(lines):
    values = config_manager.get('gitlab-search-replace', secret_name='ckan-migration-secrets', required=False)
    if values: values = json.loads(values)
    needs_update = False
    _lines = []
    for line in lines:
        if values:
            for k, v in values.items():
                if k in line:
                    logs.info(f'Search-replace gitlab line: {line} / {k} = {v}')
                    line = line.replace(k, v)
                    needs_update = True
        _lines.append(line)
    return needs_update, _lines


def instance_kind():
    crd_prefix = crds_manager.get_crd_prefix()
    return f'{crd_prefix}{INSTANCE_CRD_KIND_SUFFIX}'


def get_all_dbs_users():
    from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
    from ckan_cloud_operator.providers.db import manager as db_manager
    dbs, users = [], []
    db_host, db_port = db_manager.get_internal_unproxied_db_host_port()
    instance_db_names = []
    instance_user_names = []
    for item in DeisCkanInstance.list(quick=True, return_list=True):
        instance_id = item['id']
        instance = DeisCkanInstance(instance_id)
        spec = instance.spec
        db_name = spec.db['name']
        db_password = instance.annotations.get_secret('databasePassword')
        datastore_name = spec.datastore['name']
        datastore_password = instance.annotations.get_secret('datastorePassword')
        datastore_ro_user = instance.annotations.get_secret('datastoreReadonlyUser')
        datastore_ro_password = instance.annotations.get_secret('datatastoreReadonlyPassword')
        if all([db_name, db_password, datastore_name, datastore_password, datastore_ro_user, datastore_ro_password]):
            dbs.append((db_name, db_host, db_port))
            dbs.append((datastore_name, db_host, db_port))
            instance_db_names += [db_name, datastore_name]
            users.append((db_name, db_password))
            users.append((datastore_name, datastore_password))
            users.append((datastore_ro_user, datastore_ro_password))
            instance_user_names += [db_name, datastore_name, datastore_ro_user]
    migration_dbs, migration_users = ckan_db_migration_manager.get_all_dbs_users()
    for migration_db in migration_dbs:
        if migration_db[0] and migration_db[0] not in instance_db_names:
            dbs.append(migration_db)
    for migration_user in migration_users:
        if migration_user[0] and migration_user[0] not in instance_user_names:
            users.append(migration_user)
    return dbs, users


def get_path_to_old_cluster_kubeconfig():
    path_to_kubeconfig = '/etc/ckan-cloud/viderum-omc/.kube-config'
    if not os.path.exists(path_to_kubeconfig):
        kubeconfig = yaml.load(deis_kubeconfig())
        for filename, content in kubeconfig['__files'].items():
            if not os.path.exists(filename):
                print(f'creating file required for deis kubeconfig: {filename}')
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w') as f:
                    f.write(content)
                print('file created successfully')
        print(f'creating deis kubeconfig: {path_to_kubeconfig}')
        os.makedirs(os.path.dirname(path_to_kubeconfig), exist_ok=True)
        with open(path_to_kubeconfig, 'w') as f:
            f.write(yaml.dump(kubeconfig))
        print('created deis kubeconfig')
    return path_to_kubeconfig


def post_create_checks(instance_id):
    from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
    from ckan_cloud_operator.deis_ckan.envvars import DeisCkanInstanceEnvvars
    instance = DeisCkanInstance(instance_id)
    envvars = DeisCkanInstanceEnvvars(instance).get(full=True)
    assert envvars['ready']
    envvars = envvars['envvars']
    check_envvars(envvars, instance)


def check_envvars(envvars, deis_instance):
    from ckan_cloud_operator.providers.db import manager as db_manager
    from ckan_cloud_operator.deis_ckan.ckan import DeisCkanInstanceCKAN
    logs.info('waiting for instance to be executable...')
    for i in range(20):
        try:
            DeisCkanInstanceCKAN(deis_instance).exec('true')
            break
        except Exception:
            traceback.print_exc()
            logs.warning(f'waiting for instance exec ({i}/20)...')
            time.sleep(5)
            continue
    for url_type, url in {
        'site': envvars.get('CKAN_SITE_URL'),
        'db': envvars.get('CKAN_SQLALCHEMY_URL'),
        'datastore': envvars.get('CKAN__DATASTORE__WRITE_URL'),
        'datastore-ro': envvars.get('CKAN__DATASTORE__READ_URL'),
        'beaker': envvars.get('CKAN___BEAKER__SESSION__URL'),
        'datapusher': envvars.get('CKAN__DATAPUSHER__URL'),
        's3': envvars.get('CKANEXT__S3FILESTORE__HOST_NAME'),
        'solr': envvars.get('CKAN_SOLR_URL'),
    }.items():
        logs.info(f'checking envvar: {url_type}')
        assert url and 'None' not in url, f'invalid url: {url}'
        if url_type in ['site', 'datapusher', 's3']:
            check_cluster_url(url, verify_site_url=url_type == 'site', deis_instance=deis_instance)
        elif url_type in ['db', 'datastore', 'datastore-ro', 'beaker']:
            if '@ckan-cloud-provider-db-proxy-pgbouncer.ckan-cloud:5432' in url:
                db_manager.check_connection_string(
                    url.replace('ckan-cloud-provider-db-proxy-pgbouncer.ckan-cloud', 'localhost'))
        elif url_type == 'solr':
            from ckan_cloud_operator.providers.solr import manager as solr_manager
            assert url.startswith(solr_manager.get_internal_http_endpoint())
        else:
            raise Exception(f'unknown url type: {url_type}')


def check_cluster_url(url, verify_site_url=False, deis_instance=None):
    from ckan_cloud_operator.deis_ckan.ckan import DeisCkanInstanceCKAN
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    env_id = routers_manager.get_env_id()
    root_domain = routers_manager.get_default_root_domain()
    assert url.startswith(f'https://cc-{env_id}-') and url.rstrip('/').endswith(root_domain), f'invalid cluster url: {url}'
    if verify_site_url:
        logs.info('checking site url in running instance...')
        site_url = None
        for line in DeisCkanInstanceCKAN(deis_instance).exec('env', check_output=True).decode().splitlines():
            if line.startswith('CKAN_SITE_URL='):
                site_url = line.replace('CKAN_SITE_URL=', '').strip()
        assert site_url == url, f'mismatch between envvar and instance env: {site_url} != {url}'


def verify_instance_dbs(verify_instance_id):
    from ckan_cloud_operator.providers.db import manager as db_manager
    logs.info(f'{verify_instance_id}: Checking DB..')
    db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id))
    logs.info(f'{verify_instance_id}: Checking DataStore..')
    db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id,
                                                                                                is_datastore=True))
    logs.info(f'{verify_instance_id}: Checking DataStore ReadOnly..')
    db_manager.check_connection_string(db_manager.get_deis_instsance_external_connection_string(verify_instance_id,
                                                                                                is_datastore_readonly=True))


def ckan_admin_credentials(instance_id):
    from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
    from ckan_cloud_operator.deis_ckan.ckan import DeisCkanInstanceCKAN
    return DeisCkanInstanceCKAN(DeisCkanInstance(instance_id)).admin_credentials()


def update_deis_instance_envvars(deis_instance, envvars):
    smtp_creds = config_manager.get(secret_name='ckan-default-smtp-credentials')
    old_froms = smtp_creds.get('old-froms')
    old_froms = old_froms.split(',') if old_froms else []
    if smtp_creds and envvars.get('CKAN_SMTP_MAIL_FROM', '') in ['', smtp_creds['from']] + old_froms:
        logs.info(f'updating smtp credentials for deis instance {deis_instance.id}')
        envvars.update(CKAN_SMTP_MAIL_FROM=smtp_creds['from'],
                       CKAN_SMTP_SERVER=smtp_creds['server'],
                       CKAN_SMTP_USER=smtp_creds['user'],
                       CKAN_SMTP_PASSWORD=smtp_creds['password'])
        if envvars.get('CKANEXT__ORGPORTALS__SMTP__MAIL__FROM'):
            logs.info(f'updating orgportls smtp credentials for deis instance {deis_instance.id}')
            envvars.update(CKANEXT__ORGPORTALS__SMTP__MAIL__FROM=smtp_creds['from'],
                           CKANEXT__ORGPORTALS__SMTP__SERVER=smtp_creds['server'],
                           CKANEXT__ORGPORTALS__SMTP__USER=smtp_creds['user'],
                           CKANEXT__ORGPORTALS__SMTP__PASSWORD=smtp_creds['password'])
