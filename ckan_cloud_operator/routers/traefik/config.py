from ckan_cloud_operator import logs

import ckan_cloud_operator.routers.routes.manager as routes_manager


def _get_base_config(**kwargs):
    return dict({
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
        'file': {},
        'frontends': {},
        'backends': {},
    }, **kwargs)


def _get_acme_domains(domains, wildcard_ssl_domain=None, external_domains=False):
    for root_domain, sub_domains in domains.items():
        if external_domains:
            for sub_domain in sub_domains:
                yield {'main': f'{sub_domain}.{root_domain}'}
        elif root_domain == wildcard_ssl_domain:
            yield {
                'main': f'*.{root_domain}',
            }
        else:
            yield {
                'main': root_domain,
                'sans': [f'{sub_domain}.{root_domain}' for sub_domain in sub_domains]
            }


def _add_letsencrypt_cloudflare(config, letsencrypt_cloudflare_email, domains,
                                wildcard_ssl_domain=None, external_domains=False):
    config['defaultEntryPoints'].append('https')
    config['entryPoints']['https'] = {
        'address': ':443',
        'tls': {}
    }
    config['acme'] = {
        'email': letsencrypt_cloudflare_email,
        'storage': '/traefik-acme/acme.json',
        'entryPoint': 'https',
        **(
            {
                'tlsChallenge': {}
            } if external_domains else {
                'dnsChallenge': {
                    'provider': 'cloudflare'
                }
            }
        ),
        'domains': list(_get_acme_domains(domains, wildcard_ssl_domain=wildcard_ssl_domain,
                                          external_domains=external_domains))
    }


def _add_route(config, domains, route, enable_ssl_redirect):
    route_name = routes_manager.get_name(route)
    logs.debug(f'adding route to traefik config: {route_name}')
    logs.debug_verbose(config=config, domains=domains, route=route, enable_ssl_redirect=enable_ssl_redirect)
    backend_url = routes_manager.get_backend_url(route)
    frontend_hostname = routes_manager.get_frontend_hostname(route)
    root_domain, sub_domain = routes_manager.get_domain_parts(route)
    domains.setdefault(root_domain, []).append(sub_domain)
    if route['spec'].get('extra-no-dns-subdomains'):
        extra_hostnames = ',' + ','.join([f'{s}.{root_domain}' for s in route['spec']['extra-no-dns-subdomains']])
    else:
        extra_hostnames = ''
    logs.debug(route_name=route_name, backend_url=backend_url, frontend_hostname=frontend_hostname, root_domain=root_domain,
               sub_domain=sub_domain, domains=domains, extra_hostnames=extra_hostnames)
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
                'rule': f'Host:{frontend_hostname}{extra_hostnames}'
            }
        }
    }


def get(routes, letsencrypt_cloudflare_email, enable_access_log=False, wildcard_ssl_domain=None, external_domains=False):
    config = _get_base_config(
        **({'accessLog': {},} if enable_access_log else {})
    )
    domains = {}
    for route in routes:
        _add_route(config, domains, route, bool(letsencrypt_cloudflare_email))
    if letsencrypt_cloudflare_email:
        _add_letsencrypt_cloudflare(config, letsencrypt_cloudflare_email, domains,
                                    wildcard_ssl_domain=wildcard_ssl_domain,
                                    external_domains=external_domains)
    return config
