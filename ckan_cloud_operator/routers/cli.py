import subprocess
import yaml

from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator import logs


def add_cli_commands(click, command_group, great_success):

    @command_group.command('initialize')
    @click.option('--interactive', is_flag=True)
    def initialize(interactive):
        from ckan_cloud_operator.providers.routers.manager import initialize as manager_initialize
        manager_initialize(interactive)
        great_success()

    @command_group.command('create-traefik-router')
    @click.argument('TRAEFIK_ROUTER_NAME')
    @click.argument('DEFAULT_ROOT_DOMAIN', required=False, default='default')
    @click.argument('CLOUDFLARE_EMAIL', required=False, default='default')
    @click.argument('CLOUDFLARE_API_KEY', required=False, default='default')
    @click.option('--external-domains', is_flag=True)
    def routers_create(traefik_router_name, default_root_domain, cloudflare_email, cloudflare_api_key, external_domains):
        """Create a Traefik router, with domain registration and let's encrypt based on Cloudflare"""
        routers_manager.create(
            traefik_router_name,
            routers_manager.get_traefik_router_spec(
                default_root_domain, cloudflare_email, cloudflare_api_key,
                external_domains=external_domains
            )
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

    @command_group.command('create-ckan-instance-subdomain-route')
    @click.argument('ROUTER_NAME')
    @click.argument('CKAN_INSTANCE_ID')
    @click.argument('SUB_DOMAIN', required=False, default='default')
    @click.argument('ROOT_DOMAIN', required=False, default='default')
    @click.option('--wait-ready', is_flag=True)
    def routers_create_ckan_instance_subdomain_route(router_name, ckan_instance_id,
                                                     sub_domain, root_domain,
                                                     wait_ready):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'ckan-instance',
            'ckan-instance-id': ckan_instance_id,
            'root-domain': root_domain,
            'sub-domain': sub_domain
        })
        routers_manager.update(router_name, wait_ready)
        great_success()

    @command_group.command('create-app-instance-subdomain-route')
    @click.argument('ROUTER_NAME')
    @click.argument('APP_INSTANCE_ID')
    @click.argument('SUB_DOMAIN', required=False, default='default')
    @click.argument('ROOT_DOMAIN', required=False, default='default')
    @click.option('--wait-ready', is_flag=True)
    def routers_create_app_instance_subdomain_route(router_name, app_instance_id,
                                                    sub_domain, root_domain,
                                                    wait_ready):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'app-instance',
            'app-instance-id': app_instance_id,
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

    @command_group.command('create-backend-url-subdomain-route')
    @click.argument('ROUTER_NAME')
    @click.argument('TARGET_RESOURCE_ID')
    @click.argument('BACKEND_URL')
    @click.argument('SUB_DOMAIN', required=False, default='default')
    @click.argument('ROOT_DOMAIN', required=False, default='default')
    @click.option('--wait-ready', is_flag=True)
    @click.option('--httpauth-secret')
    def routers_create_backend_url_subdomain_route(router_name, target_resource_id, backend_url,
                                                   sub_domain, root_domain, wait_ready,
                                                   httpauth_secret):
        routers_manager.create_subdomain_route(router_name, {
            'target-type': 'backend-url',
            'target-resource-id': target_resource_id,
            'backend-url': backend_url,
            'sub-domain': sub_domain,
            'root-domain': root_domain,
            **({'httpauth-secret': httpauth_secret} if httpauth_secret else {}),
        })
        routers_manager.update(router_name, wait_ready)
        great_success()

    @command_group.command('get-routes')
    @click.option('-p', '--datapusher-name', required=False)
    @click.option('-d', '--deis-instance-id', required=False)
    @click.option('--ckan-instance-id', required=False)
    @click.option('-b', '--backend-url-target-id', required=False)
    @click.option('-o', '--one', is_flag=True)
    @click.option('-e', '--external-domain', is_flag=True)
    @click.option('--edit', is_flag=True)
    def get_routes(datapusher_name, deis_instance_id, ckan_instance_id, backend_url_target_id, one, external_domain, edit):
        if datapusher_name:
            assert not deis_instance_id and not ckan_instance_id and not backend_url_target_id
            routes = routers_manager.get_datapusher_routes(datapusher_name, edit=edit)
        elif deis_instance_id:
            assert not datapusher_name and not ckan_instance_id and not backend_url_target_id
            routes = routers_manager.get_deis_instance_routes(deis_instance_id, edit=edit)
        elif ckan_instance_id:
            assert not datapusher_name and not deis_instance_id and not backend_url_target_id
            routes = routers_manager.get_ckan_instance_routes(ckan_instance_id, edit=edit)
        elif backend_url_target_id:
            assert not datapusher_name and not deis_instance_id and not ckan_instance_id
            routes = routers_manager.get_backend_url_routes(backend_url_target_id, edit=edit)
        else:
            routes = routers_manager.get_all_routes()
        if routes:
            if one: assert len(routes) == 1, 'too many routes!'
            for route in routes:
                if external_domain:
                    data = routers_manager.get_route_frontend_hostname(route)
                    if one:
                        print(data)
                    else:
                        print(yaml.dump([data], default_flow_style=False))
                else:
                    try:
                        data = {
                            'name': route['metadata']['name'],
                            'backend-url': routes_manager.get_backend_url(route),
                            'frontend-hostname': routes_manager.get_frontend_hostname(route),
                            'router-name': route['spec']['router_name']
                        }
                    except Exception as e:
                        print('Warning: %s' % repr(e))
                        continue
                    if one:
                        print(yaml.dump(data, default_flow_style=False))
                    else:
                        print(yaml.dump([data], default_flow_style=False))

    @command_group.command('delete-routes')
    @click.option('-p', '--datapusher-name', required=False)
    @click.option('-d', '--deis-instance-id', required=False)
    @click.option('-r', '--root-domain', required=False)
    @click.option('-s', '--sub-domain', required=False)
    def delete_routes(datapusher_name, deis_instance_id, root_domain, sub_domain):
        routers_manager.delete_routes(
            datapusher_name=datapusher_name,
            deis_instance_id=deis_instance_id,
            root_domain=root_domain,
            sub_domain=sub_domain
        )
        logs.exit_great_success()

    @command_group.command('delete')
    @click.argument('ROUTER_NAME')
    @click.argument('ROUTER_TYPE', required=False, default='')
    def routers_delete(router_name, router_type):
        routers_manager.delete(router_name, router_type)
        great_success()

    @command_group.command('get')
    @click.argument('ROUTER_NAME')
    @click.option('--dns', is_flag=True)
    def get(router_name, dns):
        print(yaml.dump(routers_manager.get(router_name, only_dns=dns), default_flow_style=False))

    @command_group.command('cloudflare-rate-limits')
    @click.argument('ROOT_DOMAIN')
    def cloudflare_rate_limits(root_domain):
        logs.print_yaml_dump(routers_manager.get_cloudflare_rate_limits(root_domain))
