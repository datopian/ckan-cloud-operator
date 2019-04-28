#!/usr/bin/env bash

# to use this script, add a daemonset deployment of ubuntu:1804, running the following entrypoint:
#
# bash -c 'cp /home/ec2-user/.ssh/authorized_keys{,.bak} && echo "" > /home/ec2-user/.ssh/authorized_keys && for KEY_NAME in `ls /ec2-user-authorized-keys`; do echo $KEY_NAME && cat /ec2-user-authorized-keys/$KEY_NAME >> /home/ec2-user/.ssh/authorized_keys; done && cat /home/ec2-user/.ssh/authorized_keys && echo Great Success && while true; do sleep 86400; done'
#
# mount the relevant home directory from the node and the authorized keys secret which this script updates
#
# after updating the secret, redeploy the daemonset to apply the changes

export KEY_NAME
export KEY

echo KEY_NAME=${KEY_NAME}
echo KEY=${KEY}

[ "${KEY_NAME}" == "" ] && echo missing KEY_NAME && exit 1

[ "$(python3 -c 'import os; print("yes" if all([c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_" for c in os.environ["KEY_NAME"]]) else "no")')" != "yes" ] \
    && echo invalid characters in KEY_NAME, only upper-case letters and underscore are permitted && exit 2

[ "${KEY}" == "" ] && echo KEY is missing && exit 3

! ckan-cloud-operator config set --secret-name ec2-user-authorized-keys --namespace node-management "${KEY_NAME}" "${KEY}" \
    && echo failed to update secret && exit 4

echo Great Success!
exit 0
