CKAN Cloud Operator manages, provisions and configures CKAN Cloud instances and related infrastructure.

[TOC]

# installation

Install it with pip

```
pip install ckan-cloud-operator
```

# Complete List of commands

Show complete list of commands

```
cco
```

# Setup and Config

## cco ckan env

Add, update or remove environments. Ckan Cloud Operator is designed to work with multiple kubernetes clusters. You can easily switch between enviroments

### Usage

```
cco ckan env COMMAND [environment-name] [[--flags]]

cco ckan env
cco ckan env list
cco ckan env add     [environment-name] [[--flags]]
cco ckan env update  [environment-name] [[--flags]]
cco ckan env set     [environment-name]
cco ckan env rm      [environment-name]
```

### Commands

With no arguments show the current working environment

```
cco ckan env
> You are working with POC environment
```

#### list

Lists all existing environments

```
cco ckan env list
> POC
> DEV
> PRD
```

#### add

Adds an environment

```
cco ckan env add poc --cloud-provide cloud-provider-name \
                --environment environment-name \
                --resource-group resource-group-name \
                --cluster-name cluster-name \
                --subscription subscription-id \
                --region region-name \
                --project project-name

> XYZ environment was succefully added
```

##### Flags

- `--cloud-provide` - one of minukube, azure, gcp, aws.
- `--environment` - environment name
- `--cluster-name` - kubernetes cluster name
- `--resource-group` - **[azure only]** Azure resource group name
- `--subscription` - **[azure only]** Azure subscription id
- `--region=region-name` - **[GCP only]** GCP region id Eg: `europe-west1`
- `--project=project-name` - **[GCP only]** GCP project name

#### set

Sets given environment as a current working environment

```
cco ckan env set poc
> You are working with POC environment now
```

#### update

Update configurations for given environment

```
cco ckan env update poc --cloud-provide cloud-provider-name \
                --environment environment-name \
                --resource-group resource-group-name \
                --cluster-name cluster-name \
                --subscription subscription-id \
                --region region-name \
                --project project-name

> XYZ environment was succefully updated
```

##### Flags

Same as for `cco ckan env add`

- `--cloud-provide` - one of minukube, azure, gcp, aws.
- `--environment` - environment name
- `--cluster-name` - kubernetes cluster name
- `--resource-group` - **[azure only]** Azure resource group name
- `--subscription` - **[azure only]** Azure subscription id
- `--region=region-name` - **[GCP only]** GCP region id Eg: `europe-west1`
- `--project=project-name` - **[GCP only]** GCP project name

#### rm

Deletes given environment

```
cco ckan env rm poc
> POC environment was succesfully removed
```

## cco ckan init

Initialize ckan-cloud-operator for working with environment. This command gets all the necessary credentials for working with the given envirnment. Eg, gets and saves `kubeconfig` file in `~/.kube/config` directory

### Usage

```
cco ckan init [[--flags]]
```

#### Flags

Without flags initializes, current working environment added with `cco ckan env add`

- `--environment-name` name of the environment to initialize (one of the result of `cco ckan env list`)


```
cco ckan init --environment-name poc
> POC environment was succesfully initialized
```

# Creating And Managing Instances

## cco ckan instance

Create, Deploy and manage CKAN instances on Kubernetes Cluster

### Usage

```
cco ckan instance COMMAND [options] [[--flags]]

cco ckan instance create [options] [[--flags]]
cco ckan instance sysadmin [options] [[--flags]]
cco ckan instance solr [options] [[--flags]]
cco ckan instance ckan-exec [[--flags]]
cco ckan instance logs [[--flags]]
cco ckan instance ssh [[--flags]]
cco ckan instance shell [[--flags]]
```

### Commands

#### create

Create, update and deploy CKAN instance on kubernetes server with [Helm](https://helm.sh/)


```
cco ckan instance create [instance-type] [[values-file]] [[[--flags]]]

cco ckan instance create helm
            --instance-id datopian-sbx
            --instance-name datopian-sbx
            --exists-ok
            --dry-run
            --update
            --wait-ready
            --skip-deployment
            --skip-route
            --force
            --help
```

##### Flags

- `--instance-id` - CKAN instance id, usually matches with project name
- `--instance-name` - CKAN instance name
- `--exists-ok` - Do not fail if namespace already exists
- `--dry-run` - Run without actualy creating or deploying instance
- `--update` - Make sure instance is updated, not reqreated
- `--wait-ready` - Wait until pods are started and running fine
- `--skip-deployment` - Skip deployment
- `--skip-route` - Skip creating routes
- `--force` - Force update instance


#### sysadmin

Create or delete system administrator for CKAN instane

```
cco ckan instance sysadmin [COMMAND] USERNAME [[--flags]]
```

##### Commands

- `add` - Creates or makes given user system administrator
- `rm` - Removes System administrator privilages from given user

```
cco ckan instance sysadmin add USERNAME --pasword pasword --email email@email.com
cco ckan instance sysadmin rm USERNAME
```

##### Flags

- `--password` - Passowrd for user if user does not exist
- `--email` - Valid Email address for user if user does not exist

#### solr

Update, clear or check search index for CKAN instance

```
cco ckan instance solr [COMMANDS] [[--flags]]
```

##### Commands

- check - Check search index
- clear - Clear the search index
- rebuild - Rebuild search index
- rebuild-fast - Reindex with multiprocessing
- show - Show index of a dataset

```
cco ckan instance solr check
cco ckan instance solr clear
cco ckan instance solr rebuild
cco ckan instance solr rebuild-fast
cco ckan instance solr show --dataset=dataset-id-or-name
```

##### Flags

- `--dataset` - Dataset name to show index for

#### ckan-exec

Execute ckan CLI (former `paster`) commands.

```
cco ckan instance ckan-exec [COMMANDS]
```

##### Commands

See full list of command in [CKAN Docs](https://docs.ckan.org/en/2.9/maintaining/cli.html#ckan-commands-reference). You will need to pass full command as a string

Few examples
```
cco ckan instance ckan-exec --command='view clean --yes'
cco ckan instance ckan-exec --command='jobs list'
cco ckan instance ckan-exec --command='dataset show dataset-id'
```

##### Flags

- `--command` - command to pass down to ckan CLI, without path to config file

#### logs

Check CKAN and other service container logs

```
cco ckan instance logs [[--flags]]
```


##### Flags

- `--service`- Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`
- `--since`- Only return logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs.
- `--follow`- Specify if the logs should be streamed.
- `--tail`- Lines of recent log file to display. Defaults to -1 with no selector, showing all log lines otherwise 10, if a selector is provided.
- `--container`- Conainer name if multiple
- `--grep` - Filter logs by the given word (case insensitive)

#### ssh

SSH into the running conainer.

```
cco ckan instance ssh [[--flags]]
```

##### Flags

- `--service`- Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`
- `--command`- One of `bash`, `sh`. Defaults to `bash`

#### shell

Run Unix-like operating system commands into the running container

```
cco ckan instance shell [[--flags]]
```

##### Flags

- `--service`- Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`
- `--command`- Any valid Unix-like operating system commands

```
cco ckan instance shell --command='cat /etc/ckan/production.ini'
```

## cco ckan deployment

Create, Deploy and manage CKAN instances on Kubernetes Cluster

### Usage

```
cco ckan deployment COMMAND [options] [[--flags]]

cco ckan deployment status
cco ckan deployment logs
cco ckan deployment version
cco ckan deployment image [options] [[--flags]]
cco ckan deployment rollback [[--flags]]

```

### Commands

#### status

Shows status of the deployment. Result of `helm status release-name`

```
cco ckan deployment status
```

#### logs

Shows deployment logs

```
cco ckan deployment logs
```

#### version

Shows version of the latest succefull deployment. Same as https://site-url/version

```
cco ckan deployment version
```

#### image

Get and set CKAN or Related service images.


```
cco ckan deployment image [options] [[--flags]]
```
##### Options

- `get` - Get image name of the latest scuccesfully deployed container
- `set` - Force set given image for the given service

```
cco ckan deployment image get [[--flags]]
cco ckan deployment image set IMAGE_NAME [[--flags]]
```

##### Flags

- `--service`- Service name. One of `ckan`, `giftless`, `jobs`, `jobs-db`, `redis`. Defaults to `ckan`


## cco ckan infra

Manage and debug CKAN related infrastucrure like SOLR Cloud and Postgres Databeses

### Usage

```
cco ckan infra COMMAND [options] [[--flags]]

```

### Commands

#### solr

Check logs of SolrCloud service and restart them.

```
cco ckan infra solr [options] [[--flags]]
```

##### Options

- `logs` - See logs of SolrCloud and ZooKeeper containers
- `restart` - Restart SolrCloud and Zookeeper conaiers

```
cco ckan infra solr logs [[--flags]]
cco ckan infra solr restart [[--flags]]
```

##### Flags

- `--zookeper-only` - Make operations only for zookeper pods
- `--solrcloud-only` - Make operations only for solrcloud pods
- `--since`- Only return logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs.
- `--follow`- Specify if the logs should be streamed.
- `--tail`- Lines of recent log file to display. Defaults to -1 with no selector, showing all log lines otherwise 10, if a selector is provided.
- `--container`- Conainer name if multiple
- `--grep` - Filter logs by the given word (case insensitive)
