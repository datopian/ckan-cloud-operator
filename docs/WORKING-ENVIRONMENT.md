# Creating a CKAN-Cloud-Operator Working Environment

CKAN Cloud Operator is a Python application which relies heavily on invoking external tools such as `kubectl`, `helm`, `awscli`, `gcloud` and others.

In order to ensure that there are no version incompatibilities among the different components, we have created a few pre-built images with all the components pre-installed and with their correct versions.

## Using the Docker images

To use the docker image run this from the command line:

```bash
$ docker run -it -v $PWD/.cco:/root/ viderum/ckan-cloud-operator:latest 
```

We are mapping a directory named `.cco` in the current working directory to store important state (e.g. kubectl config, terraform state), but you can choose to map a different directory on you machine.

## Using the prebuilt AMI (for AWS)

Get the id of the latest ckan-cloud-operator AMI:

```bash
$ aws ec2  describe-images --filters "Name=name,Values=ckan-cloud-operator-*" "Name=owner-id,Values=561987031915" --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId'

"ami-0a3ed5386aa0570d7"
```

Start an instance with the image (make sure you have a valid keypair and the default security group allows SSH access):

``` 
aws ec2 run-instances 
    --image-id <ami image id>
    --count 1
    --instance-type t2.micro
    --key-name <name of keypair>
    --subnet-id <id of subnet to attach to>
    --user-data <optional user data>
```

Once instance is up and running, fetch its public DNS name:
```
$ aws ec2 describe-instances --filters "Name=image-id,Values=<ami image id>" --query "Reservations[0].Instances[0].PublicDnsName"

"ec2-aa-bb-cc-dd.eu-west-2.compute.amazonaws.com"
```

And SSH to it:
```
$ ssh ubuntu@ec2-aa-bb-cc-dd.eu-west-2.compute.amazonaws.com -i ~/.ssh/my-key-pair.pem

ubuntu@ip-aa-bb-cc-dd:~$ 
```

*A note on user data:*

You can provide an initialization script for the instance to perform in first boot by using the `user-data` argument in the `ec2 run-instances` command.

For example, you might want to use this snippet as the user data to automatically provision a cluster:

```
#!/bin/bash
cd terraform/aws
./init_cluster.sh <aws-access-key-id> <aws-secret-access-key> <aws-region> <vpc-id> <cluster-name>
```

(more info in the [AWS provisioning docs](./PRODUCTION-AWS-CLUSTER.md))

## TBD GCP Solution

## TBD GCP
