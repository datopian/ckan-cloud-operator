# Code structure
The document describes code structure for `ckan-cloud-operator` python package.

## Overview
The code has designed to work with Python >=3.7 environment (3.6 would also work, but it's not recommended).
Repository has `setup.py` file to allow installation of the package via setuptools or it could be uploaded to PyPi repo and will be available with `pip install`.

The URL of the package published on PyPi is [https://pypi.org/project/ckan-cloud-operator/](https://pypi.org/project/ckan-cloud-operator/)
If we'll update the package in near future and we want to make it upgradable via `pip install`, we need to ask Ori to give us access to his PyPi account to be able to push updated versions of `ckan-cloud-operator`.


## Main
The package installs `ckan-cloud-operator` executable which entry point is `ckan_cloud_operator.cli.main()`.
The app uses `click` library to simplify building of the command-line interface.

Package structure description could be divided into these main parts:
- Root modules
- Drivers
- Providers
- Other things


## Root modules
There're number of modules placed in `ckan_cloud_operator` root dir. Each of them contains some utils for the corresponding services.

### Cloudflare
`cloudflare` module contains utilities to update A or CNAME records via CloudFlare API and to get zone rate limits.

*First glance issues*: the way `cloudflare.is_ip()` written could produce incorrect return value for non-IP input. This validator should be rewritten, but it's not urgent

### Datapushers
`datapushers` module contains utilities to add/update/delete CkanCloudDatapusher instances built from `registry.gitlab.com/viderum/docker-datapusher` image.

### Datastore permissions
`datastore_permissions` contains raw PostgreSQL view and functions needed for fulltext search.

### GCloud
`gcloud` needed to proxy `gsutil` CLI calls.


### Gitlab
`gitlab` module initializes gitlab repo (updates `Dockerfile` inside the repo, adds `gitlab-ci.yml`)


### Infra
`infra` module declares CLI commands under `ckan-infra` group and `CkanIfra` class widely used across other modules (primary to get infrastructure env vars)


### Kubectl
`kubectl` contains number of methods that utilizes kubectl command to run actions like update configmap or secrets, create k8s objects, get status of deployment, pod name, etc.


### Log
`log` module contains self-written logging system that prints log statements only to stdout.

*First glance issues*: not sure why Ori didn't use `logger` module from standard Python lib, there're no customizations that required self-written module for logging.


### Storage
`storage` module contains functions to deploy minio proxy and permissions function to GCS. It's not used anywhere in code and not available from CLI.


### Yaml config
`yaml_config` contains methods for initial yaml lib setup.


## Drivers
Driver is a layer that communicates directly with corresponding service: by executing raw command line commands, connecting to DB, or requesting service API


### Gcloud
Does almost the same (and has duplicated code) as `gloud` root module. Has a method that activates provided services account for `gsutil`.


### Helm
Contains functions to initialize Tiller on cluster and deploy Helm charts.


### Jenkins
Contains functions to make direct POST requests to Jenkins APi


### Kubectl
Contains functions to get k8s objects and to manage cluster access control. Most of kubectl integration is in `kubectl` root module.


### Postgres
The driver connects directly to PostgreSQL (with help of psycopg2 module), and contains functions to create/delete DB, delete users, list databases and users, initialize extensions.

Additionaly there's `ckan_cloud_operator.drivers.postgredbdiff` utility that could be used standalone to compare two tables and print diff.


### Rancher
Manages Rancher things that are unrelated to the operator or cluster (creates users and tokens, cluster role template bindings)


## Providers
Each provider represents certain services that k8s operator could manage.


### CKAN
The module itself contains functions to manage CKAN instance.

It contains `db`, `deployment`, `instance`, and `storage` submodules.

- `db`: helpers for database migrations.
- `deployment`: manages CKAN instance deployments, and includes helm utilities to update/create deployments with Tiller.
- `instance`: manages CKAN instances, list/create/update/delete
- `storage`: manages minio storages, the module seems not finished (doesn't support add/update/delete)


