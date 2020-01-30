# CKAN Values File Reference

## Options Processed by CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

- `ckanHelmChartRepo` - URL for a Helm Chart Repository (uses [ckan-cloud-helm](https://github.com/ViderumGlobal/ckan-cloud-helm/tree/master/charts_repository) by default)
- `ckanHelmChartVersion` - which chart version to pick (e.g. `v0.0.15`)

- `ckanSolrSchema` - name of the solr schema to use (will use `ckan_default` by default)
- `ckanAdminEmail` - email address to use when creating the `admin` account 

- `sub-domain` - Sub domain to use for this instance (defaults to `ckan-cloud-<instance-id>`)

- `domain` - Ignored, will always be equal to `<sub-domain>.<cluster-root-domain>`
- `withSansSSL` - Ignored, will always be considered as True
- `registerSubdomain` - Ignored, will always be equal to `sub-domain`

- `imagePullSecret` - secret contains credentials for the private docker repo (secret is being created by CCO)


## Options Defined in the [standard Helm Chart](https://github.com/ViderumGlobal/ckan-cloud-helm/tree/master/ckan)

### Options that affect the CKAN deployments

- `replicas` - number of CKAN replicas to run in the instance (defaults to 2)
- `nginxReplicas` - number of Nginx replicas to run in the instance (defaults to 2)
- `ckanGunicornWorkers` - number of gunicorn workers in each CKAN instance(defaults to 2)
- `ckanResources` - Kubernetes resources object for the CKAN deployment
- `nginxResources` - Kubernetes resources object for the Nginx deployment
- `ckanJobsTerminationGracePeriodSeconds` - wait this amount of seconds before killing the ckan jobs instance
- `ckanJobsDbTerminationGracePeriodSeconds` - wait this amount of seconds before killing the ckan jobs DB instance
- `disableJobs` - Is instance-specific jobs service disabled
- `redisResources` - Kubernetes resources object for the redis server
- `ckanJobsResources` - Kubernetes resources object for the ckan jobs

- `enableHarvesterNG` - enable the NG Harvester in the deployment
- `harvesterResources` - Kubernetes resources object for the Harvester NG
- `harvesterDbResources` - Kubernetes resources object for the Harvester DB
- `harvesterDbPersistentDiskSizeGB` - Disk size for the Harvester DB

- `ckanImage` - CKAN Docker Image name and tag
- `nginxImage` - Nginx Docker Image name and tag
- `harvesterImage` - NG Harvester Docker Image name and tag
- `ckanOperatorImage` - CCA Operator Docker Image name and tag
- `themerImage` - CKAN Themer Docker Image name and tag

### Timeouts and Probing

- `terminationGracePeriodSeconds` - wait this amount of seconds before killing the CKAN instance (e.g. when upgrading)
- `noProbes` - disable readiness and liveness probing

- `ckanReadinessInitialDelaySeconds` - parameter for the readiness probe
- `ckanReadinessPeriodSeconds` - parameter for the readiness probe
- `ckanReadinessTimeoutSeconds` - parameter for the readiness probe
- `ckanReadinessFailureThreshold` - parameter for the readiness probe

- `ckanLivenessInitialDelaySeconds` - parameter for the liveness probe
- `ckanLivenessPeriodSeconds` - parameter for the liveness probe
- `ckanLivenessTimeoutSeconds` - parameter for the liveness probe
- `ckanLivenessFailureThreshold` - parameter for the liveness probe

### Options that affect CKAN's production.ini file

- `siteUrl` - value for the `ckan.site_url` CKAN configuration entry, will be automatically set according to `sub-domain`
- `siteTitle` - value for the `ckan.site_title` CKAN configuration entry
- `siteLogo` - value for the `ckan.site_logo` CKAN configuration entry
- `siteDescription` - value for the `ckan.site_description` CKAN configuration entry
- `favicon` - value for the `ckan.favIcon` CKAN configuration entry

- `displayTimezone` - value for the `ckan.display_timezone` CKAN configuration entry
- `localeDefault` - value for the `ckan.locale_default` CKAN configuration entry
- `localeOrder` - value for the `ckan.locale_order` CKAN configuration entry
- `localesOffered` - value for the `ckan.locales_offered` CKAN configuration entry
- `localesFilteredOut` - value for the `ckan.locales_filtered_out` CKAN configuration entry

- `ckanPlugins` - value for the `ckan.plugins` CKAN configuration entry (defaults to `stats text_view image_view recline_view datastore xloader`)

- `authAnon_create_dataset` - value for the `ckan.auth.anon_create_dataset` CKAN configuration entry
- `authCreate_unowned_dataset` - value for the `ckan.auth.create_unowned_dataset` CKAN configuration entry
- `authCreate_dataset_if_not_in_organization` - value for the `ckan.auth.create_dataset_if_not_in_organization` CKAN configuration entry
- `authUser_create_groups` - value for the `ckan.auth.user_create_groups` CKAN configuration entry
- `authUser_create_organizations` - value for the `ckan.auth.user_create_organizations` CKAN configuration entry
- `authUser_delete_groups` - value for the `ckan.auth.user_delete_groups` CKAN configuration entry
- `authUser_delete_organizations` - value for the `ckan.auth.user_delete_organizations` CKAN configuration entry
- `authCreate_user_via_api` - value for the `ckan.auth.create_user_via_api` CKAN configuration entry
- `authCreate_user_via_web` - value for the `ckan.auth.create_user_via_web` CKAN configuration entry
- `authRoles_that_cascade_to_sub_groups` - value for the `ckan.auth.roles_that_cascade_to_sub_groups` CKAN configuration entry

- `extraCkanConfig` - content to be added verbatim into the production.ini file

### Other Configurations

- `useCloudStorage` - use a cloud storage bucket for storing CKAN files
- `ckanPrimaryColor` - set the newly created ckan theme to be based on this color (hex based RGB, e.g. `#123456`)
- `cronjobs` - list of CronJob entries to be created on the cluster

### Internal 

- `debugMode` - enable debug mode in the instance 
- `envVarsSecretName` - Name of kubernetes secret containing CKAN configuration env vars
- `ckanSecretName` - Name of kubernetes secret containing other CKAN secrets
- `centralizedSecretName` - Name of kubernetes secret containing Centralized Infra Services secrets
- `centralizedSolrHost` - Hostname for centralized Solr Server 
- `centralizedSolrPort` - Port for centralized Solr Server
- `ckanCloudInstanceId` - Instance ID, automatically set by CCO
- `usePersistentVolumes` - Should the instance use persistent volumes or host paths
- `ckanStorageClassName` - Kubernetes storage class name to use when provisioning persistent volumes
- `centralizedInfraOnly` - should always be set to false

### Deprecated

- `useCentralizedInfra` - should always be set to true
- `dbTerminationGracePeriodSeconds` - wait this amount of seconds before killing the ckan DB instance
- `datastoreDbTerminationGracePeriodSeconds` - wait this amount of seconds before killing the datastore DB instance
- `dbDisabled` - Is instance-specific DB disabled
- `solrDisabled` - Is instance-specific SOLR disabled
- `dbImage` - Docker Image and Tag for Postgres DB
- `solrcloudImage` - Docker Image and Tag for SolrCloud
- `dbResources` - Kubernetes resources object for the ckan db
- `solrResources` - Kubernetes resources object for the SolrCloud
- `ckanJobsDbResources` - Kubernetes resources object for the ckan jobs db
- `datastoreDbResources` - Kubernetes resources object for the datastore db
- `datastorePublicreadonlyDbUserPasswordSecretName` - TBD
- `dbPersistentDiskSizeGB` - Size of ckan DB disk size
- `jobsDbPersistentDiskSizeGB` - Size of ckan jobs DB disk size
- `dataStoreDbPersistentDiskSizeGB` - Size of datastore DB disk size
- `solrPersistentDiskSizeGB` - Size of SolrCloud disk size

