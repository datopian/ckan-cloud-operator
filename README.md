# CKAN Cloud Operator

CKAN Cloud operator manages, provisions and configures Ckan Cloud instances and related infrastructure.

## Install

ckan-cloud-operator-env is used to install and manage CKAN Cloud operator environments on your local PC

The only requirement is a .kube-config file with permissions to the relevant cluster

Install ckan-cloud-operator-env

```
curl https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-operator/master/ckan-cloud-operator-env.sh \
    | sudo tee /usr/local/bin/ckan-cloud-operator-env &&\
sudo chmod +x /usr/local/bin/ckan-cloud-operator-env
```

Pull the latest Docker image

```
ckan-cloud-operator-env pull
```

Add an environment (to run on Minikube set PATH_TO_KUBECONFIG_FILE to minikube)

```
sudo ckan-cloud-operator-env add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE>
```

Verify you are connected to the correct cluster

```
ckan-cloud-operator cluster-info
```

## Usage

Use the CLI help messages or the [CLI source code](ckan_cloud_operator/cli.py) for the reference documentation and usage examples.

```
ckan-cloud-operator --help
ckan-cloud-operator deis-instance --help
.
.
```

Start a bash shell with completion

```
ckan-cloud-operator bash
```

This start a bash shell inside the ckan-cloud-operator Docker container, you can use bash completion inside this shell

```
ckan-cloud-operator <TAB><TAB>
```

## Managing multiple environments

ckan-cloud-operator-env supports managing multiple environments

Add environments using `ckan-cloud-operator-env add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE>`

Each environment is accessible using executable `ckan-cloud-operator-<ENVIRONMENT_NAME>`

Activating an environment sets the `ckan-cloud-operator` executable to use to the relevant environment executable

```
ckan-cloud-operator-env activate <ENVIRONMENT_NAME>
```

## Initializing a cluster for ckan-cloud-operator

Kubernetes custom resource definitions are used for management of the CKAN Cloud resources

Run the following command to ensure the crds are installed on the cluster

```
ckan-cloud-operator install-crds
```

ckan-cloud-operator using a secret named `ckan-infra` under namespace `ckan-cloud` to get infrastrutcute secrets.

See the list of values in [ckan_cloud_operator/infra.py](ckan_cloud_operator/infra.py)

You can clone an infrastructure secret using `ckan-infra clone` command
and some infrastructure secrets can be set using `ckan-infra set` command

## Run ckan-cloud-operator locally

Ensure you have `kubectl` and `gcloud` binaries, authenticated to the relevant gcloud account / kubernetes cluster.

See the required system dependencies: [environment.yaml](environment.yaml)

You can [Install miniconda3](https://conda.io/miniconda.html), then create the environment using: `conda env create -f environment.yaml`

Activate the conda environment using `conda activate ckan-cloud-operator`

Install the Python package:

```
python3 -m pip install -e .
```

Authenticate the gcloud CLI to the relevant account:

```
ckan-cloud-operator activate-gcloud-auth
```

Run ckan-cloud-operator without arguments to get a help message:

```
ckan-cloud-operator
```

Enable Bash completion

```
eval "$(ckan-cloud-operator bash-completion)"
```
