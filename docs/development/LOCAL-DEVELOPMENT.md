## Local Development

### Using the Docker image

This is the preferred solution as it ensures you have a consistent environment.

Build the image using the command for your target environment:

* AWS:

```
docker build -t ckan-cloud-operator .
```

* Minikube:

```
docker build -t ckan-cloud-operator \
    --build-arg K8_PROVIDER=minikube \
    .
```

Custom (e.g. using the `kamatera` custom provider):

```
docker build -t ckan-cloud-operator \
    --build-arg K8_PROVIDER=custom-kamatera \
    --build-arg K8_PROVIDER_CUSTOM_DOWNLOAD_URL=https://github.com/OriHoch/cco-provider-kamatera/archive/v0.0.1.tar.gz \
    .
```

Start a bash shell:

```
docker run -it -v $PWD/.cco:/root/ -v $PWD:/cco ckan-cloud-operator 
```

For development of custom providers, add the following argument:

```
-v /path/to/custom-provider-repo:/usr/local/lib/cco/$K8_PROVIDER
``` 

Install the Python package for development:

```
pip install -e .
```

For custom providers, install the custom provider package:

```
pip install -e /usr/local/lib/cco/$K8_PROVIDER
```

Run ckan-cloud-operator commands, any changes in .py files will be reflected inside the container:

```
ckan-cloud-operator --help
```

Enable Bash completion

```
eval "$(ckan-cloud-operator bash-completion)"
```

### Without Docker

Ensure you have all required dependencies according to the Dockerfile, related scripts and build-args for the target environment.

Install the Python package:

```
pip install -e .
```

Run ckan-cloud-operator commands

```
ckan-cloud-operator --help
```

Enable Bash completion

```
eval "$(ckan-cloud-operator bash-completion)"
```

### Using Jupyter Lab

Jupyter Lab can be used to run bulk operations or aggregate data from ckan-cloud-operator

You should run ckan-cloud-operator locally and run the following from the activated ckan-cloud-operator environment

Install jupyterlab

```
pip install jupyterlab
```

Run jupyterlab

```
jupyter lab
```

Open notebooks from the `notebooks` directory

### Run tests

If you already have `ckan-cloud-operator` executable in your PATH, you could run test suite with `ckan-cloud-operator test` command.

The other way to run test suite is `coverage run -m unittest discover`.
