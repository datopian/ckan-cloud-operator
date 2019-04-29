#!/usr/bin/env bash

cp /home/ec2-user/.ssh/authorized_keys{,.bak}

echo "" > /home/ec2-user/.ssh/authorized_keys

for KEY_NAME in `ls /ec2-user-authorized-keys`; do
    echo | tee -a /home/ec2-user/.ssh/authorized_keys
    echo "# ${KEY_NAME}" | tee -a /home/ec2-user/.ssh/authorized_keys
    echo | tee -a /home/ec2-user/.ssh/authorized_keys
    cat /ec2-user-authorized-keys/$KEY_NAME | tee -a /home/ec2-user/.ssh/authorized_keys
    echo | tee -a /home/ec2-user/.ssh/authorized_keys
done

cat /home/ec2-user/.ssh/authorized_keys

echo
echo Great Success

while true; do sleep 86400; done
