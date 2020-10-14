import traceback

from ckan_cloud_operator import logs

import ckan_cloud_operator.routers.routes.manager as routes_manager


def _get_base_config(**kwargs):
    logs.info('Generating base Traefik configuration', **kwargs)
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


def _add_letsencrypt(dns_provider, config, letsencrypt_cloudflare_email, domains,
                     wildcard_ssl_domain=None, external_domains=False):
    logs.info('Adding Letsencrypt acme Traefik configuration', dns_provider=dns_provider,
              letsencrypt_cloudflare_email=letsencrypt_cloudflare_email, domains=domains,
              wildcard_ssl_domain=wildcard_ssl_domain, external_domains=external_domains)
    assert dns_provider in ['route53', 'cloudflare', 'azure']
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
                    'provider': dns_provider
                }
            }
        ),
        'domains': list(_get_acme_domains(domains, wildcard_ssl_domain=wildcard_ssl_domain,
                                          external_domains=external_domains))
    }


def _add_route(config, domains, route, enable_ssl_redirect):
    route_name = routes_manager.get_name(route)
    logs.info(f'adding route to traefik config: {route_name}')
    logs.debug_verbose(config=config, domains=domains, route=route, enable_ssl_redirect=enable_ssl_redirect)
    backend_url = routes_manager.get_backend_url(route)
    frontend_hostname = routes_manager.get_frontend_hostname(route)
    print(f'F/B = {frontend_hostname} {backend_url}')
    root_domain, sub_domain = routes_manager.get_domain_parts(route)
    domains.setdefault(root_domain, []).append(sub_domain)
    if route['spec'].get('extra-no-dns-subdomains'):
        extra_hostnames = ',' + ','.join([f'{s}.{root_domain}' for s in route['spec']['extra-no-dns-subdomains']])
    else:
        extra_hostnames = ''
    logs.debug_verbose(route_name=route_name, backend_url=backend_url, frontend_hostname=frontend_hostname, root_domain=root_domain,
                       sub_domain=sub_domain, domains=domains, extra_hostnames=extra_hostnames)
    if backend_url:
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
            },
            **({
                'auth': {
                    'basic': {
                        'usersFile': '/httpauth-' + route['spec']['httpauth-secret'] + '/.htpasswd'
                    }
                }
            } if route['spec'].get('httpauth-secret') else {}),
        }


def get(routes, letsencrypt_cloudflare_email, enable_access_log=False, wildcard_ssl_domain=None, external_domains=False,
        dns_provider=None, force=False):
    if not dns_provider:
        dns_provider = 'cloudflare'
    logs.info('Generating traefik configuration', routes_len=len(routes) if routes else 0,
              letsencrypt_cloudflare_email=letsencrypt_cloudflare_email, enable_access_log=enable_access_log,
              wildcard_ssl_domain=wildcard_ssl_domain, external_domains=external_domains)
    config = _get_base_config(
        **(
            {
                'accessLog': {
                    "format": "json",
                    "fields": {
                        'defaultMode': "keep"
                    }
                },
            }
            if enable_access_log else {}
        )
    )
    domains = {}
    if dns_provider == 'cloudflare' and letsencrypt_cloudflare_email:
        enable_ssl_redirect = True
    elif dns_provider == 'route53':
        enable_ssl_redirect = True
    elif dns_provider == 'azure':
        enable_ssl_redirect = True
    else:
        enable_ssl_redirect = False
    logs.info(enable_ssl_redirect=enable_ssl_redirect)
    logs.info('Adding routes')
    i = 0
    errors = 0
    for route in routes:
        try:
            _add_route(config, domains, route, enable_ssl_redirect)
            i += 1
        except Exception as e:
            if force:
                logs.error(traceback.format_exc())
                logs.error(str(e))
                errors += 1
            else:
                raise
    logs.info(f'Added {i} routes')
    if errors > 0:
        logs.warning(f'Encountered {errors} errors')
    if (
        (dns_provider == 'cloudflare' and letsencrypt_cloudflare_email)
        or (dns_provider == 'route53')
        or (dns_provider == 'azure')
    ):
        _add_letsencrypt(dns_provider, config, letsencrypt_cloudflare_email, domains,
                         wildcard_ssl_domain=wildcard_ssl_domain, external_domains=external_domains)
    else:
        logs.info('No valid dns_provider, will not setup SSL', dns_provider=dns_provider)
    return config
