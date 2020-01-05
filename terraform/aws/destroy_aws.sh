#!/bin/sh
for vid in `aws ec2 describe-volumes | jq '.Volumes[] | .VolumeId' -r` ; do echo $vid ; aws ec2 delete-volume --volume-id "$vid"; done
for lb in `aws elb describe-load-balancers | jq '.LoadBalancerDescriptions[] | .LoadBalancerName' -r` ; do echo $lb ; aws elb delete-load-balancer --load-balancer-name "$lb"; done
./terraform destroy -auto-approve
