# Creating a Production CKAN Cloud cluster using Amazon Kubernetes service

## Prerequisites

* An Amazon Account with admin privileges and matching access and secret keys.
* An existing VPC with an existing subnet in each availability zone
* An external domain registered to Amazon Route53
* A CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

## Provision the cluster

### Terraform

In the CCO environment, go to the `terraform/aws` directory.

There you can find `main.tf`, which is a Terraform configuration file to provision a CCO cluster and some peripheral services.

It contains initializations for:
- an EKS cluster with a node-group of 3 nodes
- an RDS instance to serve as a centralized database for CKAN instance on a `db.m4.large` machine
- an EFS filesystem for creating volumes containing configurations that need to be sheared among containers
- all necessary security groups and IAM roles

you could use this file as-is or tweak it based on your needs and requirements.

To apply the configuration, use `terraform apply`. You will need to set some input variables as environment variables (or create a `terraform.tfvars` file - see Terraform's docs for more info), like so:

```bash
export TF_VAR_aws_access_key_id="..."        # AWS Access Key
export TF_VAR_aws_secret_access_key="..."    # AWS Secret Access Key
export TF_VAR_region="..."                   # Region where to apply (e.g. 'us-east-1')
export TF_VAR_vpc_id="..."                   # ID of the VPC where to apply 
export TF_VAR_cluster_name="..."             # Name of the cluster to create

./terraform apply
```

Once Terraform completes, it will generate a CCO initialization parameter object.
You can save it to a file like so:

```
./terraform output cco-interactive-yaml > interactive.yaml
```

A `kubectl` configuration is also created in the process, and it will be saved in the local directory as `kubeconfig_<cluster-name>`.
You should copy it to `~/.kube/config` or set the `KUBECONFIG` environment variable to point to it.

### CCO Provision Cluster

Once Terraform finishes the cluser setup, we can use CCO to initialize the cluster itself.

CCO initialize will:
- Create all necessary K8S objects and configurations
- Run required services on the cluster (DB proxy, EFS provisioner, SOLR Cloud etc.) and initialize them properly.

For an unattended initialization, using the outputs of `terraform apply`, run:

```bash
export CCO_INTERACTIVE_CI=interactive.yaml
ckan-cloud-operator cluster initialize --cluster-provider=aws
```

You can also run the same without setting the `CCO_INTERACTIVE_CI` environment variable for an interactive initialization session.
