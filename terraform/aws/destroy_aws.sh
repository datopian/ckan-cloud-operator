#!/bin/sh
export AWS_DEFAULT_REGION=eu-west-2
export TF_VAR_vpc_id="vpc-30aedd58"
for vid in `aws ec2 describe-volumes | jq '.Volumes[] | .VolumeId' -r` ; do echo $vid ; aws ec2 delete-volume --volume-id "$vid"; done
for lb in `aws elb describe-load-balancers | jq '.LoadBalancerDescriptions[] | .LoadBalancerName' -r` ; do echo $lb ; aws elb delete-load-balancer --load-balancer-name "$lb"; done
./terraform destroy -auto-approve
