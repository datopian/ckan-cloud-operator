# DNS providers

## Adding a new DNS integration
1. To store DNS provider API token as a secret in the cluster, add `config_interactive_set` calls to cluster initialization code.
2. Implement a function that calls DNS provider API and creates A records (see the `ckan_cloud_operator.cloudflare.update_a_record` or `ckan_cloud_operator.providers.cluster.aws.manager.update_dns_record`)
3. Update routes code to call previously implemented function when needed.
