import subprocess
import yaml

from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import kubectl


def add_cli_commands(click, command_group, great_success):

    @command_group.command('create-traefik-router')
    @click.argument('TRAEFIK_ROUTER_NAME')
    @click.argument('DEFAULT_ROOT_DOMAIN', required=False, default='default')
    @click.argument('CLOUDFLARE_EMAIL', required=False, default='default')
    @click.argument('CLOUDFLARE_API_KEY', required=False, default='default')
    def routers_create(traefik_router_name, default_root_domain, cloudflare_email, cloudflare_api_key):
        """Create a Traefik router, with domain registration and let's encrypt based on Cloudflare"""
        routers_manager.create(
            traefik_router_name,
            routers_manager.get_traefik_router_spec(default_root_domain, cloudflare_email, cloudflare_api_key)
        )
        routers_manager.update(traefik_router_name)
        great_success()

    @command_group.command('update')
    @click.argument('ROUTER_NAME')
    @click.option('--wait-ready', is_flag=True)
    def routers_update(router_name, wait_ready):
        """Update a router to latest resource spec"""
        routers_manager.update(router_name, wait_ready)
        great_success()

    @command_group.command('list')
    @click.option('-f', '--full', is_flag=True)
    @click.option('-v', '--values-only', is_flag=True)
    def routers_list(**kwargs):
        """List the router resources"""
        routers_manager.list(**kwargs)

    @command_group.command('kubectl-get-all')
    @click.argument('ROUTER_TYPE', default=routers_manager.DEFAULT_ROUTER_TYPE)
    def routers_kubectl_get_all(router_type):
        subprocess.check_call(f'kubectl -n ckan-cloud get all -l ckan-cloud/router-type={router_type}',
                              shell=True)

    @command_group.command('create-deis-instance-subdomain-route')
    @click.argument('ROUTER_NAME')
    @click.argument('DEIS_INSTANCE_ID')
    @click.argument('SUB_DOMAIN', required=False, default='default')
    @click.argument('ROOT_DOMAIN', required=False, default='default')
    @click.option('--wait-ready', is_flag=True)
    def routers_create_deis_instance_subdomain_route(router_name, deis_instance_id,
                                                     sub_domain, root_domain,
                                                     wait_ready):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'deis-instance',
            'deis-instance-id': deis_instance_id,
            'root-domain': root_domain,
            'sub-domain': sub_domain
        })
        routers_manager.update(router_name, wait_ready)
        great_success()

    @command_group.command('create-datapusher-subdomain-route')
    @click.argument('ROUTER_NAME')
    @click.argument('DATAPUSHER_NAME')
    @click.argument('SUB_DOMAIN', required=False, default='default')
    @click.argument('ROOT_DOMAIN', required=False, default='default')
    @click.option('--wait-ready', is_flag=True)
    def routers_create_datapusher_subdomain_route(router_name, datapusher_name,
                                                  sub_domain, root_domain,
                                                  wait_ready):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'datapusher',
            'datapusher-name': datapusher_name,
            'root-domain': root_domain,
            'sub-domain': sub_domain
        })
        routers_manager.update(router_name, wait_ready)
        great_success()

    @command_group.command('get-routes')
    @click.option('-p', '--datapusher-name', required=False)
    @click.option('-d', '--deis-instance-id', required=False)
    def get_routes(datapusher_name, deis_instance_id):
        if datapusher_name:
            assert not deis_instance_id
            routes = routers_manager.get_datapusher_routes(datapusher_name)
        elif deis_instance_id:
            routes = routers_manager.get_deis_instance_routes(deis_instance_id)
        else:
            raise Exception(f'invalid arguments')
        if routes:
            for route in routes:
                data = {
                    'name': route['metadata']['name'],
                    'backend-url': routes_manager.get_backend_url(route),
                    'frontend-hostname': routes_manager.get_frontend_hostname(route),
                }
                print(yaml.dump([data], default_flow_style=False))

    @command_group.command('delete')
    @click.argument('ROUTER_NAME')
    @click.argument('ROUTER_TYPE', required=False, default='')
    def routers_delete(router_name, router_type):
        routers_manager.delete(router_name, router_type)
        great_success()

    @command_group.command('get')
    @click.argument('ROUTER_NAME')
    def get(router_name):
        print(yaml.dump(routers_manager.get(router_name), default_flow_style=False))
