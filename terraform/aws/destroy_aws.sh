#!/bin/sh
export AWS_DEFAULT_REGION=eu-west-2
export TF_VAR_vpc_id="vpc-30aedd58"
for vid in `aws ec2 describe-volumes | jq '.Volumes[] | .VolumeId' -r` ; do echo $vid ; aws ec2 delete-volume --volume-id "$vid"; done
for lb in `aws elb describe-load-balancers | jq '.LoadBalancerDescriptions[] | .LoadBalancerName + " " + .VPCId' -r | grep vpc-30aedd58 | cut -d' ' -f1` ; do echo $lb ; aws elb delete-load-balancer --load-balancer-name "$lb"; done
aws s3 ls | cut -d" " -f 3 | grep -v persistent | xargs -I{} aws s3 rb s3://{}
./terraform destroy -auto-approve
