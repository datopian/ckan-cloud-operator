# CKAN Cloud Operator

CKAN Cloud Operator manages, provisions and configures CKAN Cloud instances and related infrastructure.

## Components

- Terraform configurations for first setup of a Kubernets cluster and peripheral services for multiple cloud providers:
  - AWS
  - GCP
  - Azure
  - Minikube for local development
- `ckan-cloud-operator` CLI will manage the cluster and any other services necessary for day-to-day operations
- Management server, comes preinstalled with ckan-cloud-operator, required tools (terraform, kubectl, helm, awscli etc.) and [a Jenkins Server](/docs/JENKINS.md).

## Quick Start

In order to start using ckan-cloud-operator, you need to
1. [Create a CKAN Cloud Operator working environment](docs/WORKING-ENVIRONMENT.md).

   You can choose to: 
   - Use our pre-built Docker image
   - Run the AMI (on AWS)
   - Run the TBD (on GCP)
   - Run the TBD (on Azure)

   Note: While technically possible, we recommend not to run ckan-cloud-operator directly on you machine to avoid version incompatibilities between the various tools involved in the process. You should use one of our pre-built images or our Docker image instead.

2. Create a Kubernetes cluster and provision it.
    - [Instructions for AWS](docs/PRODUCTION-AWS-CLUSTER.md):
        - Create a cluster using terraform
        - Initialize the cluster using ckan-cloud-operator

    - Instructions for GCP:
        - Create a cluster using terraform
        - Initialize the cluster using ckan-cloud-operator
    
    - [Instructions for Azure](docs/PRODUCTION-AZURE-CLUSTER.md):
        - Create a cluster using terraform
        - Initialize the cluster using ckan-cloud-operator
    
    - Instructions for Minikube:
        - Initialize the cluster using ckan-cloud-operator

3. Then you can [create a CKAN Instance on the cluster](docs/CREATE-CKAN-INSTANCE.md):
    - Create a values file
    - Create the instance on the cluster

4. (Optional) [Set-up Jenkins and the Provisioning UI](docs/PROVISIONING-SERVER.md)

## Reference

- Command Line Interface parameters
- [CKAN Values file reference](docs/VALUES-FILE-REFERENCE.md)
