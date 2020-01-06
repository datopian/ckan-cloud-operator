#!/bin/sh
for vid in `aws ec2 describe-volumes | jq '.Volumes[] | .VolumeId' -r` ; do echo $vid ; aws ec2 delete-volume --volume-id "$vid"; done
for lb in `aws elb describe-load-balancers | jq '.LoadBalancerDescriptions[] | .LoadBalancerName' -r` ; do echo $lb ; aws elb delete-load-balancer --load-balancer-name "$lb"; done
aws s3 ls | cut -d" " -f 3 | xargs -I{} aws s3 rb s3://{}
./terraform destroy -auto-approve
