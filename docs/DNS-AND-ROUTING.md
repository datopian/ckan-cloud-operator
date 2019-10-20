# DNS and Routing
The document describes how CCO helps manage DNS records and set up routing.

## Overview
CCO sets up Traefik on a cluster when you run cluster initialization command.

There're 2 Traefik instances:
- The first one manages routes to infrastructure instances (minio, jenkins, zoonavigator, etc).
- The second one manages routes to CKAN instances.

When you create or update a CKAN instance, CCO makes an API call to the DNS provider to create an A record.  
After that CCO reconfigures Traefik config file to point a domain to the instance, and creates a Lets Encrypt SSL certificate.  

## Supported DNS providers
- CloudFlare
- Route 53
- UltraDNS

Code reference: `ckan_cloud_operator/routers`, `ckan_cloud_operator/providers/cluster/<cloud_provider_name>`

## Adding a new DNS integration
1. To store DNS provider API token as a secret in the cluster, add `config_interactive_set` calls to cluster initialization code.
2. Implement a function that calls DNS provider API and creates A records (see the `ckan_cloud_operator.cloudflare.update_a_record` or `ckan_cloud_operator.providers.cluster.aws.manager.update_dns_record`)
3. Update routes code to call previously implemented function when needed.
