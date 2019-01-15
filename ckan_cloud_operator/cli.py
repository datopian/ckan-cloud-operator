import sys
import json
import yaml
import traceback
import subprocess
import tempfile
import os
import click
from xml.etree import ElementTree
from ckan_cloud_operator.deis_ckan.instance import DeisCkanInstance
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator import gcloud
from ckan_cloud_operator import kubectl
from ckan_cloud_operator.gitlab import CkanGitlab
import ckan_cloud_operator.routers
import ckan_cloud_operator.users
import ckan_cloud_operator.storage


CLICK_CLI_MAX_CONTENT_WIDTH = 200


def great_success():
    print('Great Success!')
    exit(0)


#################################
####                         ####
####           main          ####
####                         ####
#################################


@click.group(context_settings={'max_content_width': CLICK_CLI_MAX_CONTENT_WIDTH})
def main():
    """Manage, provision and configure CKAN Clouds and related infrastructure"""
    pass


@main.command()
@click.option('-f', '--full', is_flag=True)
def cluster_info(full):
    """Get information about the cluster"""
    subprocess.check_call('kubectl cluster-info && '
                          '( kubectl -n ckan-cloud get secret ckan-infra || true ) && '
                          'kubectl config get-contexts $(kubectl config current-context) && '
                          'kubectl get nodes', shell=True)
    if full:
        infra = CkanInfra()
        output = gcloud.check_output(f'sql instances describe {infra.GCLOUD_SQL_INSTANCE_NAME} --format=json',
                                     project=infra.GCLOUD_SQL_PROJECT)
        data = yaml.load(output)
        print(yaml.dump({'gcloud_sql': {'connectionName': data['connectionName'],
                                        'databaseVersion': data['databaseVersion'],
                                        'gceZone': data['gceZone'],
                                        'ipAddresses': data['ipAddresses'],
                                        'name': data['name'],
                                        'project': data['project'],
                                        'region': data['region'],
                                        'selfLink': data['selfLink'],
                                        'state': data['state']}}))
        output = subprocess.check_output(f'curl {infra.SOLR_HTTP_ENDPOINT}/admin/collections?action=LIST', shell=True)
        if output:
            root = ElementTree.fromstring(output.decode())
            print('solr-collections:')
            for e in root.find('arr').getchildren():
                print(f'- {e.text}')
        else:
            raise Exception()


@main.command()
def install_crds():
    """Install ckan-cloud-operator custom resource definitions"""
    DeisCkanInstance.install_crd()
    ckan_cloud_operator.routers.install_crds()
    ckan_cloud_operator.users.install_crds()
    great_success()


@main.command()
@click.argument('GITLAB_PROJECT_NAME')
def initialize_gitlab(gitlab_project_name):
    """Initialize the gitlab integration"""
    CkanGitlab(CkanInfra()).initialize(gitlab_project_name)
    great_success()


@main.command()
def activate_gcloud_auth():
    """Authenticate with gcloud CLI using the ckan-cloud-operator credentials"""
    infra = CkanInfra()
    gcloud_project = infra.GCLOUD_AUTH_PROJECT
    service_account_email = infra.GCLOUD_SERVICE_ACCOUNT_EMAIL
    service_account_json = infra.GCLOUD_SERVICE_ACCOUNT_JSON
    if all([gcloud_project, service_account_email, service_account_json]):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(service_account_json.encode())
        try:
            gcloud.check_call(
                f'auth activate-service-account {service_account_email} --key-file={f.name}',
                with_activate=False
            )
        except Exception:
            traceback.print_exc()
        os.unlink(f.name)
        exit(0)
    else:
        print('missing gcloud auth details')
        exit(1)


@main.command()
def bash_completion():
    """Return bash completion script which should be eval'd"""
    subprocess.check_call('echo "$(_CKAN_CLOUD_OPERATOR_COMPLETE=source ckan-cloud-operator)"', shell=True)
    print('# ')
    print('# To enable Bash completion, use the following command:')
    print('# eval "$(ckan-cloud-operator bash-completion)"')


@main.command()
def initialize_storage():
    """Initialize the centralized storage bucket"""
    ckan_infra = CkanInfra()
    bucket_name = ckan_infra.GCLOUD_STORAGE_BUCKET
    project_id = ckan_infra.GCLOUD_AUTH_PROJECT
    function_name = bucket_name.replace('-', '') + 'permissions'
    function_js = ckan_cloud_operator.storage.PERMISSIONS_FUNCTION_JS(function_name, project_id, bucket_name)
    package_json = ckan_cloud_operator.storage.PERMISSIONS_FUNCTION_PACKAGE_JSON
    print(f'bucket_name = {bucket_name}\nproject_id={project_id}\nfunction_name={function_name}')
    print(package_json)
    print(function_js)
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f'{tmpdir}/package.json', 'w') as f:
            f.write(package_json)
        with open(f'{tmpdir}/index.js', 'w') as f:
            f.write(function_js)
        gcloud.check_call(
            f'functions deploy {function_name} '
                               f'--runtime nodejs6 '
                               f'--trigger-resource {bucket_name} '
                               f'--trigger-event google.storage.object.finalize '
                               f'--source {tmpdir} '
                               f'--retry '
                               f'--timeout 30s '
        )


#################################
####                         ####
####         users           ####
####                         ####
#################################


@main.group()
def users():
    """Manage ckan-cloud-operator users"""
    pass


@users.command('create')
@click.argument('NAME')
@click.argument('ROLE')
def users_create(name, role):
    ckan_cloud_operator.users.create(name, role)
    ckan_cloud_operator.users.update(name)
    great_success()


@users.command('update')
@click.argument('NAME')
def users_update(name):
    ckan_cloud_operator.users.update(name)
    great_success()


@users.command('get')
@click.argument('NAME')
def users_get(name):
    print(yaml.dump(ckan_cloud_operator.users.get(name), default_flow_style=False))


@users.command('delete')
@click.argument('NAME')
def users_delete(name):
    ckan_cloud_operator.users.delete(name)


@users.command('list')
@click.argument('ARGS', nargs=-1)
def users_list(args):
    kubectl.call('get CkanCloudUser ' + ' '.join(args))


#################################
####                         ####
####       ckan-infra        ####
####                         ####
#################################


@main.group()
def ckan_infra():
    """Manage the centralized infrastructure"""
    pass


@ckan_infra.command('clone')
def ckan_infra_clone():
    """Clone the infrastructure secret from an existing secret piped on stdin

    Example: KUBECONFIG=/other/.kube-config kubectl -n ckan-cloud get secret ckan-infra -o yaml | ckan-cloud-operator ckan-infra clone
    """
    CkanInfra.clone(yaml.load(sys.stdin.read()))
    great_success()


@ckan_infra.group('set')
def ckan_infra_set():
    """Set or overwrite infrastructure secrets"""
    pass


@ckan_infra_set.command('gcloud')
@click.argument('GCLOUD_SERVICE_ACCOUNT_JSON_FILE')
@click.argument('GCLOUD_SERVICE_ACCOUNT_EMAIL')
@click.argument('GCLOUD_AUTH_PROJECT')
def ckan_infra_set_gcloud(*args):
    """Sets the Google cloud authentication details, should run locally or mount the json file into the container"""
    CkanInfra.set('gcloud', *args)
    great_success()


@ckan_infra_set.command('docker-registry')
@click.argument('DOCKER_REGISTRY_SERVER')
@click.argument('DOCKER_REGISTRY_USERNAME')
@click.argument('DOCKER_REGISTRY_PASSWORD')
@click.argument('DOCKER_REGISTRY_EMAIL')
def ckan_infra_set_docker_registry(*args):
    """Sets the Docker registry details for getting private images for CKAN pods in the cluster"""
    CkanInfra.set('docker-registry', *args)
    great_success()


@ckan_infra.command('get')
def ckan_infra_get():
    """Get the ckan-infra secrets"""
    print(yaml.dump(CkanInfra.get(), default_flow_style=False))


@ckan_infra.command('admin-db-connection-string')
def ckan_infra_admin_db_connection_string():
    """Get a DB connection string for administration

    Example: psql -d $(ckan-cloud-operator admin-db-connection-string)
    """
    infra = CkanInfra()
    postgres_user = infra.POSTGRES_USER
    postgres_password = infra.POSTGRES_PASSWORD
    postgres_host = infra.POSTGRES_HOST
    postgres_port = '5432'
    db = sys.argv[3] if len(sys.argv) > 3 else ''
    print(f'postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{db}')


#################################
####                         ####
####     deis-instance       ####
####                         ####
#################################


@main.group()
def deis_instance():
    """Manage Deis CKAN instance resources"""
    pass


@deis_instance.command('list')
@click.option('-f', '--full', is_flag=True)
def deis_instance_list(full):
    """List the Deis instances"""
    DeisCkanInstance.list(full)


@deis_instance.command('get')
@click.argument('INSTANCE_ID')
@click.argument('ATTR', required=False)
def deis_instance_get(instance_id, attr):
    """Get detailed information about an instance, optionally returning only a single get attribute

    Example: ckan-cloud-operator get <INSTANCE_ID> deployment
    """
    print(yaml.dump(DeisCkanInstance(instance_id).get(attr), default_flow_style=False))


@deis_instance.command('edit')
@click.argument('INSTANCE_ID')
@click.argument('EDITOR', default='nano')
def deis_instance_edit(instance_id, editor):
    """Launch an editor to modify and update an instance"""
    subprocess.call(f'EDITOR={editor} kubectl -n ckan-cloud edit DeisCkanInstance/{instance_id}', shell=True)
    DeisCkanInstance(instance_id).update()
    great_success()


@deis_instance.command('update')
@click.argument('INSTANCE_ID')
@click.argument('OVERRIDE_SPEC_JSON', required=False)
@click.option('--persist-overrides', is_flag=True)
@click.option('--wait-ready', is_flag=True)
def deis_instance_update(instance_id, override_spec_json, persist_overrides, wait_ready):
    """Update an instance to the latest resource spec, optionally applying the given json override to the resource spec

    Examples:

    ckan-cloud-operator update <INSTANCE_ID> '{"envvars":{"CKAN_SITE_URL":"http://localhost:5000"}}' --wait-ready

    ckan-cloud-operator update <INSTANCE_ID> '{"flags":{"skipDbPermissions":false}}' --persist-overrides
    """
    override_spec = json.loads(override_spec_json) if override_spec_json else None
    DeisCkanInstance(instance_id, override_spec=override_spec, persist_overrides=persist_overrides).update(wait_ready=wait_ready)
    great_success()


@deis_instance.command('delete')
@click.argument('INSTANCE_ID', nargs=-1)
@click.option('--force', is_flag=True)
def deis_instance_delete(instance_id, force):
    """Permanently delete the instances and all related infrastructure"""
    for id in instance_id:
        try:
            DeisCkanInstance(id).delete(force)
        except Exception:
            traceback.print_exc()
    great_success()


#### deis-instance create


@deis_instance.group('create')
def deis_instance_create():
    """Create and update an instance"""
    pass


@deis_instance_create.command('from-gitlab')
@click.argument('GITLAB_REPO_NAME')
@click.argument('SOLR_CONFIG_NAME')
@click.argument('NEW_INSTANCE_ID')
def deis_instance_create_from_gitlab(gitlab_repo_name, solr_config_name, new_instance_id):
    """Create and update a new instance from a GitLab repo containing Dockerfile and .env

    Example: ckan-cloud-operator deis-isntance create --from-gitlab viderum/cloud-demo2 ckan_27_default <NEW_INSTANCE_ID>
    """
    DeisCkanInstance.create('from-gitlab', gitlab_repo_name, solr_config_name, new_instance_id).update()
    great_success()


@deis_instance_create.command('from-gcloud-envvars')
@click.argument('PATH_TO_INSTANCE_ENV_YAML')
@click.argument('IMAGE')
@click.argument('SOLR_CONFIG')
@click.argument('GCLOUD_DB_URL')
@click.argument('GCLOUD_DATASTORE_URL')
@click.argument('STORAGE_PATH')
@click.argument('NEW_INSTANCE_ID')
def deis_instance_create_from_gcloud_envvars(
                                        path_to_instance_env_yaml,
                                        image,
                                        solr_config,
                                        gcloud_db_url,
                                        gcloud_datastore_url,
                                        storage_path,
                                        new_instance_id):
    """Create and update an instance from existing DB dump stored in gcloud sql format on google cloud storage.

    Example:

        ckan-cloud-operator deis-instance create from-gcloud-envvars "/path/to/configs/my-instance.yaml" "registry.gitlab.com/viderum/cloud-my-instance" "ckan_default" "gs://.." "gs://.." "/path/in/central/google/storage/bucket" "my-new-instance-id"
    """
    DeisCkanInstance.create(
        'from-gcloud-envvars',
        path_to_instance_env_yaml,
        image,
        solr_config,
        gcloud_db_url,
        gcloud_datastore_url,
        storage_path,
        new_instance_id
    ).update()
    great_success()


#### deis-instance ckan


@deis_instance.group('ckan')
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
    DeisCkanInstance(instance_id).ckan.run('paster', *paster_args)


@deis_instance_ckan.command('port-forward')
@click.argument('INSTANCE_ID')
@click.argument('PORT', default='5000')
def deis_instance_port_forward(instance_id, port):
    """Start a port-forward to the CKAN instance pod"""
    DeisCkanInstance(instance_id).ckan.run('port-forward', port)


@deis_instance_ckan.command('exec')
@click.argument('INSTANCE_ID')
@click.argument('KUBECTL_EXEC_ARGS', nargs=-1)
def deis_instance_ckan_exec(instance_id, kubectl_exec_args):
    """Run kubectl exec on the first CKAN instance pod"""
    DeisCkanInstance(instance_id).ckan.run('exec', *kubectl_exec_args)


@deis_instance_ckan.command('logs')
@click.argument('INSTANCE_ID')
@click.argument('KUBECTL_LOGS_ARGS', nargs=-1)
def deis_instance_ckan_logs(instance_id, kubectl_logs_args):
    """Run kubectl logs on the first CKAN instance pod"""
    DeisCkanInstance(instance_id).ckan.run('logs', *kubectl_logs_args)


#################################
####                         ####
####       routers           ####
####                         ####
#################################


@main.group()
def routers():
    """Manage CKAN Cloud routers"""
    pass


@routers.command('create')
@click.argument('ROUTER_NAME')
@click.argument('ROUTER_TYPE', default='traefik')
def routers_create(router_name, router_type):
    """Create a router, uses `traefik` router type by default"""
    ckan_cloud_operator.routers.create(router_name, router_type)
    great_success()


@routers.command('update')
@click.argument('ROUTER_NAME')
@click.option('--wait-ready', is_flag=True)
def routers_update(router_name, wait_ready):
    """Update a router to latest resource spec"""
    ckan_cloud_operator.routers.update(router_name, wait_ready)
    great_success()


@routers.command('list')
@click.option('-f', '--full', is_flag=True)
@click.option('-v', '--values-only', is_flag=True)
def routers_list(**kwargs):
    """List the router resources"""
    ckan_cloud_operator.routers.list(**kwargs)


@routers.command('kubectl-get-all')
@click.argument('ROUTER_TYPE', default='traefik')
def routers_kubectl_get_all(router_type):
    assert router_type in ['traefik']
    subprocess.check_call(f'kubectl -n ckan-cloud get all -l ckan-cloud/router-type={router_type}',
                          shell=True)

@routers.group('traefik')
def routers_traefik():
    """Manage traefik routers"""
    pass

@routers_traefik.command('enable-letsencrypt-cloudflare')
@click.argument('TRAEFIK_ROUTER_NAME')
@click.argument('EMAIL')
@click.argument('API_KEY')
@click.option('--wait-ready', is_flag=True)
def routers_traefik_enable_letsencrypt_cloudflare(traefik_router_name, email, api_key, wait_ready):
    ckan_cloud_operator.routers.traefik(
        'enable-letsencrypt-cloudflare',
        traefik_router_name,
        (email, api_key)
    )
    ckan_cloud_operator.routers.update(traefik_router_name, wait_ready)
    great_success()


@routers_traefik.command('set-deis-instance-subdomain-route')
@click.argument('TRAEFIK_ROUTER_NAME')
@click.argument('DEIS_INSTANCE_ID')
@click.argument('ROOT_DOMAIN')
@click.argument('SUB_DOMAIN')
@click.argument('ROUTE_NAME')
@click.option('--wait-ready', is_flag=True)
def routers_traefik_set_deis_instance_route(traefik_router_name, deis_instance_id, root_domain,
                                            sub_domain, route_name, wait_ready):
    deis_instance = DeisCkanInstance(deis_instance_id)
    ckan_cloud_operator.routers.traefik(
        'set-deis-instance-subdomain-route',
        traefik_router_name,
        (deis_instance, root_domain, sub_domain, route_name)
    )
    ckan_cloud_operator.routers.update(traefik_router_name, wait_ready)
    great_success()


@routers.command('get')
@click.argument('ROUTER_NAME')
def get(router_name):
    print(yaml.dump(ckan_cloud_operator.routers.get(router_name), default_flow_style=False))
