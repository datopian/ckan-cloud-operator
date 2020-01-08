
## Install

`ckan-cloud-operator-env` is used to install and manage CKAN Cloud operator environments on your local PC

**Prerequisites:**

* `.kube-config` file with permissions to the relevant cluster

Install latest ckan-cloud-operator-env

```
curl -s https://raw.githubusercontent.com/datopian/ckan-cloud-operator/master/ckan-cloud-operator-env.sh \
| sudo tee /usr/local/bin/ckan-cloud-operator-env >/dev/null && sudo chmod +x /usr/local/bin/ckan-cloud-operator-env
```

Add an environment (sudo is required to install the executable)

```
sudo ckan-cloud-operator-env add <ENVIRONMENT_NAME> <PATH_TO_KUBECONFIG_FILE>
```

Verify conection to the cluster and installed operator version (may take a while on first run or after upgrade of operator version)

```
ckan-cloud-operator cluster info
```

**Important** Re-run the add command and cluster info to verify compatible version is installed.

## Usage

Use the CLI help messages for the reference documentation and usage examples.

```
ckan-cloud-operator --help
ckan-cloud-operator deis-instance --help
.
.
```

You can use bash completion inside this shell

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

## Using Jupyter Lab

Jupyter Lab can be used to run bulk operations or aggregate data from ckan-cloud-operator

You should run ckan-cloud-operator locally and run the following from the activated ckan-cloud-operator environment

Install jupyterlab

```
python3 -m pip install jupyterlab
```

Run jupyterlab

```
jupyter lab
```

Open notebooks from the `notebooks` directory

## Run tests
If you already have `ckan-cloud-operator` executable in your PATH, you could run test suite with `ckan-cloud-operator test` command.

The other way to run test suite is `coverage run -m unittest discover`.
