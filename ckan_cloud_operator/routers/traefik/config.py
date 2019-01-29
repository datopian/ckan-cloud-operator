import ckan_cloud_operator.routers.routes.manager as routes_manager


def _get_base_config():
    return {
        'debug': False,
        'defaultEntryPoints': ['http'],
        'entryPoints': {
            'http': {
                'address': ':80'
            }
        },
        'ping': {
            'entryPoint': 'http'
        },
        'accessLog': {},
        'file': {},
        'frontends': {},
        'backends': {},
    }


def _add_letsencrypt_cloudflare(config, letsencrypt_cloudflare_email, domains):
    config['defaultEntryPoints'].append('https')
    config['entryPoints']['https'] = {
        'address': ':443',
        'tls': {}
    }
    config['acme'] = {
        'email': letsencrypt_cloudflare_email,
        'storage': '/traefik-acme/acme.json',
        'entryPoint': 'https',
        'dnsChallenge': {
            'provider': 'cloudflare'
        },
        'domains': [{
            'main': root_domain,
            'sans': [f'{sub_domain}.{root_domain}' for sub_domain in sub_domains]
        } for root_domain, sub_domains in domains.items()]
    }


def _add_route(config, domains, route, enable_ssl_redirect):
    route_name = routes_manager.get_name(route)
    backend_url = routes_manager.get_backend_url(route)
    frontend_host = routes_manager.get_frontend_host(route)
    root_domain, sub_domain = routes_manager.get_domain_parts(route)
    domains.setdefault(root_domain, []).append(sub_domain)
    config['backends'][route_name] = {
        'servers': {
            'server1': {
                'url': backend_url
            }
        }
    }
    config['frontends'][route_name] = {
        'backend': route_name,
        'passHostHeader': True,
        'headers': {
            'SSLRedirect': bool(enable_ssl_redirect)
        },
        'routes': {
            'route1': {
                'rule': f'Host:{frontend_host}'
            }
        }
    }


def get(annotations, routes):
    config = _get_base_config()
    letsencrypt_cloudflare_enabled = bool(annotations.get_flag('letsencryptCloudflareEnabled'))
    domains = {}
    for route in routes:
        _add_route(config, domains, route, letsencrypt_cloudflare_enabled)
    if letsencrypt_cloudflare_enabled:
        _add_letsencrypt_cloudflare(config, annotations.get_secret('LETSENCRYPT_CLOUDFLARE_EMAIL'), domains)
    return config
